"""`POST documents/{id}/ocr/`: the request, its quota arithmetic and its refusals (no Tesseract needed: nothing runs here)."""
# ruff: noqa: F811 - pytest fixtures imported from `ocr_export_support` are redefined as test arguments

import threading
import uuid
from datetime import UTC, datetime

import pytest
from django.db import connection

from core.models import Job
from modules.coverage.tests.conftest import OTHER, USER
from modules.notes.errors import QuotaExceeded
from modules.notes.models import Document, FileContent, FilePage, MonthlyUsage
from modules.notes.services import ocr, quota

from .ocr_export_support import fake_storage, make_pdf_document, scanned_document  # noqa: F401
from .worker.fixtures import make_pdfs as mk

pytestmark = pytest.mark.django_db
URL = "/notes/documents/{}/ocr/"


def used(user=USER) -> int:
    row = MonthlyUsage.objects.filter(user_id=user).first()
    return row.ocr_pages if row else 0


@pytest.fixture
def scan(fake_storage, tmp_path):
    return scanned_document(fake_storage, USER, tmp_path, pages=12)


def test_it_charges_the_pages_queues_the_first_chunk_and_answers_202(api, scan):
    res = api.post(URL.format(scan.id), {"mode": "tesseract"})
    assert res.status_code == 202, res.json_body
    assert res.json_body == {"status": "pending", "ocr_pages_total": 12, "charged_pages": 12, "estimate_seconds": 72}
    assert used() == 12
    content = FileContent.objects.get(pk=scan.content_id)
    assert (content.ocr_status, content.ocr_pages_total, content.ocr_pages_done) == ("pending", 12, 0)
    assert content.ocr_engine == "tesseract-5.1:eng"
    scan.refresh_from_db()
    assert (scan.ocr_mode, scan.ocr_lang) == ("tesseract", "eng")
    job = Job.objects.get(type="notes.ocr")
    assert job.dedupe_key == f"notes.ocr:{content.id}" and job.priority == ocr.FIRST_CHUNK_PRIORITY
    assert job.payload["spec"] == "1-12" and job.payload["pages"] == [1, 10]
    assert job.payload["lang"] == "eng" and job.payload["content_id"] == str(content.id)


def test_hindi_is_opt_in_per_request_and_stored_on_the_document_and_engine(api, scan):
    api.post(URL.format(scan.id), {"mode": "tesseract", "lang": "eng+hin", "pages": "1-4"})
    scan.refresh_from_db()
    assert scan.ocr_lang == "eng+hin"
    assert FileContent.objects.get(pk=scan.content_id).ocr_engine.endswith(":eng+hin")


def test_the_student_default_language_applies_when_none_is_sent(api, scan):
    api.put("/notes/settings/", {"ocr_lang": "eng+hin"})
    api.post(URL.format(scan.id), {"mode": "tesseract"})
    assert Job.objects.get(type="notes.ocr").payload["lang"] == "eng+hin"


def test_a_page_selection_is_validated_against_the_page_count(api, scan):
    for bad in ("13", "0", "5-2", "x"):
        res = api.post(URL.format(scan.id), {"mode": "tesseract", "pages": bad})
        assert res.status_code == 422 and res.json_body["error"]["code"] == "invalid_pages", bad
    assert used() == 0 and not Job.objects.filter(type="notes.ocr").exists()
    ok = api.post(URL.format(scan.id), {"mode": "tesseract", "pages": "1-3,12"})
    assert ok.json_body["charged_pages"] == 4 and Job.objects.get().payload["spec"] == "1-3,12"


def test_ai_mode_and_bad_bodies(api, scan):
    ai = api.post(URL.format(scan.id), {"mode": "ai"})
    assert ai.status_code == 403 and ai.json_body["error"]["code"] == "feature_disabled"
    assert api.post(URL.format(scan.id), {}).status_code == 400
    assert api.post(URL.format(scan.id), {"mode": "tesseract", "lang": "fra"}).status_code == 400
    assert used() == 0


def test_401_and_cross_user_404(api, other_api, scan, client):
    assert client.post("/api/v1" + URL.format(scan.id), content_type="application/json").status_code == 401
    res = other_api.post(URL.format(scan.id), {"mode": "tesseract"})
    assert res.status_code == 404
    assert api.post(URL.format(uuid.uuid4()), {"mode": "tesseract"}).status_code == 404
    assert used(OTHER) == 0


def test_a_trashed_document_is_not_found(api, scan):
    Document.objects.filter(pk=scan.pk).update(deleted_at=datetime.now(UTC))
    assert api.post(URL.format(scan.id), {"mode": "tesseract"}).status_code == 404


def test_locked_files_answer_409(api, fake_storage, tmp_path):
    path = mk.text_pdf(tmp_path / "t.pdf")
    doc = make_pdf_document(fake_storage, USER, path, is_encrypted=True, page_count=None, text_status="locked")
    Document.objects.filter(pk=doc.pk).update(status="needs_password")
    res = api.post(URL.format(doc.id), {"mode": "tesseract"})
    assert res.status_code == 409 and res.json_body["error"]["code"] == "locked"
    assert used() == 0


def test_a_file_not_inspected_yet_is_not_ready(api, fake_storage, tmp_path):
    doc = make_pdf_document(fake_storage, USER, mk.text_pdf(tmp_path / "t.pdf"))
    Document.objects.filter(pk=doc.pk).update(content=None, status="inspecting")
    res = api.post(URL.format(doc.id), {"mode": "tesseract"})
    assert res.status_code == 409 and res.json_body["error"]["code"] == "not_ready"


def test_a_copy_restricted_file_is_not_read_by_ocr(api, scan):
    FileContent.objects.filter(pk=scan.content_id).update(can_copy=False)
    res = api.post(URL.format(scan.id), {"mode": "tesseract"})
    assert res.status_code == 422 and res.json_body["error"]["code"] == "ocr_not_allowed"
    assert used() == 0


def test_a_text_pdf_has_nothing_to_ocr(api, fake_storage, tmp_path):
    doc = make_pdf_document(fake_storage, USER, mk.text_pdf(tmp_path / "t.pdf", pages=4))
    for n in range(1, 5):
        FilePage.objects.create(content=doc.content, page=n, text="Plenty of native text on this page " + "x" * 30)
    res = api.post(URL.format(doc.id), {"mode": "tesseract"})
    assert res.status_code == 422 and res.json_body["error"]["code"] == "not_scanned_or_no_pages"
    assert used() == 0 and not Job.objects.exists()


def test_pages_with_native_text_are_left_alone_and_not_charged(api, scan):
    for n in (1, 2, 3):
        FilePage.objects.create(content=scan.content, page=n, text="Some native text that is long enough here")
    FilePage.objects.create(content=scan.content, page=4, text="tiny")  # a scan's stray characters do not protect it
    res = api.post(URL.format(scan.id), {"mode": "tesseract"})
    assert res.json_body["charged_pages"] == 9 and Job.objects.get().payload["spec"] == "4-12"


def test_pages_already_read_are_skipped_and_an_active_request_is_not_charged_twice(api, scan):
    api.post(URL.format(scan.id), {"mode": "tesseract", "pages": "1-6"})
    assert used() == 6
    again = api.post(URL.format(scan.id), {"mode": "tesseract", "pages": "4-9"})
    assert again.json_body["charged_pages"] == 3 and used() == 9  # 7 to 9 only: 4 to 6 are already promised
    repeat = api.post(URL.format(scan.id), {"mode": "tesseract", "pages": "1-9"})
    assert repeat.status_code == 202 and repeat.json_body["charged_pages"] == 0 and used() == 9
    assert repeat.json_body["status"] == "pending"
    assert Job.objects.filter(type="notes.ocr").count() == 2  # no third chain for pages that are all queued
    keys = sorted(Job.objects.values_list("dedupe_key", flat=True))
    assert keys[0].startswith(f"notes.ocr:{scan.content_id}") and len(set(keys)) == 2


def test_a_second_student_with_the_same_bytes_is_done_instantly_and_pays_nothing(api, other_api, scan, fake_storage):
    FilePage.objects.bulk_create(
        FilePage(content=scan.content, page=n, text="ocr text", text_source="ocr", ocr_conf=90) for n in range(1, 13)
    )
    FileContent.objects.filter(pk=scan.content_id).update(
        ocr_status="done", ocr_pages_done=12, ocr_pages_total=12, ocr_engine="tesseract-5.1:eng"
    )
    twin = make_pdf_document(fake_storage, OTHER, _path_of(scan, fake_storage, OTHER), content=scan.content)
    res = other_api.post(URL.format(twin.id), {"mode": "tesseract"})
    assert res.status_code == 202
    assert res.json_body == {"status": "done", "ocr_pages_total": 12, "charged_pages": 0, "estimate_seconds": 0}
    assert used(OTHER) == 0 and not Job.objects.exists()
    twin.refresh_from_db()
    assert twin.ocr_mode == "tesseract"


def _path_of(doc, fake, user):
    """A temp file holding the document's bytes, so a twin document can be created for another student."""
    import tempfile
    from pathlib import Path

    data = fake.objects[(doc.attachment.bucket, doc.attachment.path)]
    target = Path(tempfile.mkdtemp()) / "twin.pdf"
    target.write_bytes(data)
    return target


def test_an_english_result_does_not_cover_hindi_and_the_pages_are_redone(api, scan):
    FilePage.objects.bulk_create(
        FilePage(content=scan.content, page=n, text="ocr", text_source="ocr", ocr_conf=80) for n in (1, 2)
    )
    FileContent.objects.filter(pk=scan.content_id).update(
        ocr_status="done", ocr_pages_done=2, ocr_pages_total=2, ocr_engine="tesseract-5.1:eng"
    )
    res = api.post(URL.format(scan.id), {"mode": "tesseract", "lang": "eng+hin", "pages": "3-4"})
    assert res.json_body["charged_pages"] == 4  # pages 3 and 4 plus the two read as English
    content = FileContent.objects.get(pk=scan.content_id)
    assert content.ocr_engine.endswith("eng+hin") and content.ocr_pages_done == 0
    assert Job.objects.get().payload["since"] is not None
    # and an English request on Hindi-read text needs nothing
    FilePage.objects.filter(content=scan.content).update(text_source="ocr")


def test_the_monthly_limit_answers_429_with_the_quota_details(api, scan):
    quota_limit = quota.ocr_pages_per_month(USER)
    MonthlyUsage.objects.create(user_id=USER, month=_this_month(), ocr_pages=quota_limit - 5)
    res = api.post(URL.format(scan.id), {"mode": "tesseract", "pages": "1-6"})
    assert res.status_code == 429
    err = res.json_body["error"]
    assert err["code"] == "quota_exceeded"
    assert err["details"]["kind"] == "ocr" and err["details"]["used"] == quota_limit - 5
    assert err["details"]["limit"] == quota_limit and err["details"]["plan"] == "free"
    assert len(err["details"]["resets_on"]) == 10
    assert used() == quota_limit - 5 and not Job.objects.exists()  # a refused request changes nothing
    ok = api.post(URL.format(scan.id), {"mode": "tesseract", "pages": "1-5"})
    assert ok.status_code == 202 and used() == quota_limit  # exactly at the limit still fits


def _this_month():
    from django.utils import timezone

    from modules.notes.domain.quota import month_start

    return month_start(timezone.now())


def test_a_failed_charge_rolls_back_everything(api, scan, monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("queue down")

    monkeypatch.setattr("core.jobs.enqueue", boom)
    with pytest.raises(RuntimeError):
        ocr.request_ocr(USER, scan.id, mode="tesseract")
    assert used() == 0
    assert FileContent.objects.get(pk=scan.content_id).ocr_status == "none"


@pytest.mark.django_db(transaction=True, serialized_rollback=True)
def test_two_requests_for_the_last_pages_admit_exactly_one(api, fake_storage, tmp_path):
    if connection.vendor != "postgresql":
        pytest.skip("needs row locks")
    one = scanned_document(fake_storage, USER, tmp_path, pages=6)
    two = scanned_document(fake_storage, USER, tmp_path, pages=6, lines=("DIFFERENT TEXT", "ON THESE PAGES"))
    limit = quota.ocr_pages_per_month(USER)
    MonthlyUsage.objects.create(user_id=USER, month=_this_month(), ocr_pages=limit - 6)
    results: list = []
    barrier = threading.Barrier(2)

    def attempt(document):
        try:
            barrier.wait(timeout=10)
            results.append(ocr.request_ocr(USER, document.id, mode="tesseract"))
        except QuotaExceeded as exc:
            results.append(exc)
        finally:
            connection.close()

    threads = [threading.Thread(target=attempt, args=(d,)) for d in (one, two)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(30)
    assert sum(isinstance(r, ocr.OcrRequest) for r in results) == 1
    assert sum(isinstance(r, QuotaExceeded) for r in results) == 1
    assert used() == limit
    assert Job.objects.filter(type="notes.ocr").count() == 1
