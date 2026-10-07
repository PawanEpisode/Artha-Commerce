"""
The job glue with the worker libraries stubbed: every result and error code of the inspection maps to the right document state,
and the extract job's chunking, chaining, rank rule and failure handling hold, independent of what the real parsers do.
"""

import hashlib
import uuid

import pytest

from core import jobs
from core.models import Job
from modules.media.models import Attachment
from modules.notes import jobs_pdf
from modules.notes.models import Document, FileContent, FilePage, QuotaUsage
from modules.notes.worker import extract as worker_extract
from modules.notes.worker import inspect as pdf_inspect
from modules.notes.worker.inspect import InspectResult
from modules.notes.worker.pdfutil import PdfOpenError, PdfPasswordRequired

from .documents_support import MB
from .factories import ALICE, make_attachment, make_content, make_document

pytestmark = pytest.mark.django_db

DATA = b"%PDF-1.4 stand-in for a real file"


def inspecting(fake, user=ALICE, data=DATA, **fields) -> Document:
    """A document the worker is about to inspect: a clean attachment with bytes in the fake store and quota held for it."""
    attachment = make_attachment(user, bytes=len(data))
    fake.upload(attachment.bucket, attachment.path, data, content_type="application/pdf", cache_control="")
    row = QuotaUsage.objects.get_or_create(user_id=user)[0]
    QuotaUsage.objects.filter(pk=row.pk).update(bytes_used=row.bytes_used + len(data), docs_active=row.docs_active + 1)
    return make_document(user, attachment=attachment, status="inspecting", page_count=None, **fields)


def ok(data=DATA, pages=4, **over) -> InspectResult:
    base = {
        "ok": True,
        "page_count": pages,
        "page_meta": tuple({"w": 595.0, "h": 842.0} for _ in range(pages)),
        "outline": ({"title": "Ch 1", "page": 1, "children": []},),
        "can_copy": True,
        "can_modify": True,
        "is_scanned": False,
        "text_pct": 100,
        "sha256": hashlib.sha256(data).hexdigest(),
        "bytes": len(data),
        "cover_webp": b"RIFFxxxxWEBP",
        "engine_version": "stub",
    }
    return InspectResult(**{**base, **over})


@pytest.fixture
def stub_inspect(monkeypatch):
    holder = {"result": ok()}

    def fake(path, **kwargs):
        value = holder["result"]
        if isinstance(value, Exception):
            raise value
        return value

    monkeypatch.setattr(pdf_inspect, "inspect_pdf", fake)
    return holder


def usage():
    row = QuotaUsage.objects.get(pk=ALICE)
    return row.bytes_used, row.docs_active


@pytest.mark.parametrize("code", ["type_mismatch", "pdf_corrupt", "too_many_pages", "decode_failed", "policy"])
def test_every_error_code_rejects_with_that_reason_and_releases_the_quota(fake_storage, stub_inspect, code):
    doc = inspecting(fake_storage)
    stub_inspect["result"] = InspectResult(ok=False, error_code=code)
    assert jobs_pdf.inspect_job({"document_id": str(doc.id)}) == {"rejected": code}
    doc.refresh_from_db()
    assert (doc.status, doc.status_reason) == ("rejected", code)
    assert usage() == (0, 0) and not fake_storage.objects
    assert Attachment.objects.get(pk=doc.attachment_id).status == "rejected"
    assert jobs_pdf.inspect_job({"document_id": str(doc.id)}) == {
        "skipped": "rejected"
    }  # a replay releases nothing more
    assert usage() == (0, 0)


def test_an_unknown_error_code_becomes_policy(fake_storage, stub_inspect):
    doc = inspecting(fake_storage)
    stub_inspect["result"] = InspectResult(ok=False, error_code="something_new")
    jobs_pdf.inspect_job({"document_id": str(doc.id)})
    assert Document.objects.get(pk=doc.pk).status_reason == "policy"


def test_needs_password_keeps_the_file_and_locks_the_text(fake_storage, stub_inspect):
    doc = inspecting(fake_storage)
    stub_inspect["result"] = InspectResult(
        ok=True, is_encrypted=True, needs_password=True, sha256="a" * 64, bytes=len(DATA)
    )
    assert jobs_pdf.inspect_job({"document_id": str(doc.id)}) == {"status": "needs_password"}
    doc.refresh_from_db()
    assert doc.status == "needs_password" and doc.content.text_status == "locked" and doc.content.is_encrypted
    assert (
        doc.content.page_meta is None
        and usage() == (len(DATA), 1)
        and not Job.objects.filter(type="notes.extract_text")
    )


def test_a_clean_result_makes_the_document_ready_and_queues_extraction_once(fake_storage, stub_inspect):
    doc = inspecting(fake_storage)
    assert jobs_pdf.inspect_job({"document_id": str(doc.id)}) == {"status": "ready", "pages": 4, "shared": False}
    doc.refresh_from_db()
    assert (doc.status, doc.page_count) == ("ready", 4) and doc.content.page_meta[0] == {"w": 595.0, "h": 842.0}
    assert doc.content.outline[0]["title"] == "Ch 1" and doc.content.is_scanned is False and doc.content.text_pct == 100
    assert doc.cover_attachment_id and Attachment.objects.get(pk=doc.cover_attachment_id).kind == "note_image"
    queued = Job.objects.filter(type="notes.extract_text")
    assert queued.count() == 1 and queued.get().payload == {
        "content_id": str(doc.content_id),
        "document_id": str(doc.id),
    }


def test_content_with_text_already_done_skips_extraction(fake_storage, stub_inspect):
    existing = make_content(
        sha256=hashlib.sha256(DATA).hexdigest(), page_count=4, page_meta=[{"w": 1, "h": 1}] * 4, text_status="done"
    )
    doc = inspecting(fake_storage)
    assert jobs_pdf.inspect_job({"document_id": str(doc.id)}) == {"status": "ready", "pages": 4, "shared": True}
    assert Document.objects.get(pk=doc.pk).content_id == existing.pk and FileContent.objects.count() == 1
    assert not Job.objects.filter(type="notes.extract_text")


def test_more_pages_than_the_plan_allows_is_rejected_for_uploads_only(fake_storage, stub_inspect):
    stub_inspect["result"] = ok(pages=1001)
    mine = inspecting(fake_storage)
    assert jobs_pdf.inspect_job({"document_id": str(mine.id)}) == {"rejected": "too_many_pages"}
    platform = inspecting(fake_storage, user=uuid.uuid4(), origin="platform", bytes=0)
    assert jobs_pdf.inspect_job({"document_id": str(platform.id)})["status"] == "ready"  # our own file: no plan limit


def test_a_file_bigger_than_the_reservation_is_rejected_too_large(fake_storage, stub_inspect):
    doc = inspecting(fake_storage)
    stub_inspect["result"] = ok(bytes=len(DATA) + 1)
    assert jobs_pdf.inspect_job({"document_id": str(doc.id)}) == {"rejected": "too_large"}
    assert usage() == (0, 0)


def test_an_object_far_over_its_declared_size_is_rejected_before_the_parser_runs(
    fake_storage, stub_inspect, monkeypatch
):
    doc = inspecting(fake_storage)
    Attachment.objects.filter(pk=doc.attachment_id).update(bytes=10)
    monkeypatch.setattr("modules.notes.services.objects.SLACK_BYTES", 0)
    stub_inspect["result"] = RuntimeError("the parser must not be reached")
    assert jobs_pdf.inspect_job({"document_id": str(doc.id)}) == {"rejected": "too_large"}


def test_a_missing_object_is_retried_not_judged(fake_storage, stub_inspect):
    doc = inspecting(fake_storage)
    fake_storage.objects.clear()
    with pytest.raises(Exception, match="rror|empty|missing|404"):
        jobs_pdf.inspect_job({"document_id": str(doc.id)})
    assert Document.objects.get(pk=doc.pk).status == "inspecting" and usage() == (len(DATA), 1)


def test_a_parser_crash_is_retried_and_fails_the_document_on_the_last_attempt(fake_storage, stub_inspect, monkeypatch):
    doc = inspecting(fake_storage)
    stub_inspect["result"] = ValueError("pdfium blew up")
    with pytest.raises(ValueError):
        jobs_pdf.inspect_job({"document_id": str(doc.id)})
    assert Document.objects.get(pk=doc.pk).status == "inspecting"
    job = jobs.enqueue("notes.inspect", {"document_id": str(doc.id)})
    job.attempts = job.max_attempts
    monkeypatch.setattr(jobs_pdf.core_jobs, "current_job", lambda: job)
    with pytest.raises(ValueError):
        jobs_pdf.inspect_job({"document_id": str(doc.id)})
    doc.refresh_from_db()
    assert (doc.status, doc.status_reason) == ("failed", "decode_failed") and usage() == (
        len(DATA),
        1,
    )  # keeps its quota


def test_a_document_that_is_gone_or_not_waiting_is_skipped(fake_storage, stub_inspect):
    assert jobs_pdf.inspect_job({"document_id": str(uuid.uuid4())}) == {"skipped": "gone"}
    reserved = make_document(ALICE, status="reserved")
    assert jobs_pdf.inspect_job({"document_id": str(reserved.id)}) == {"skipped": "reserved"}
    unclean = make_document(ALICE, status="inspecting", attachment=make_attachment(ALICE, status="uploaded"))
    assert jobs_pdf.inspect_job({"document_id": str(unclean.id)}) == {"skipped": "not_clean"}


def test_no_cover_is_made_when_the_student_is_at_the_storage_limit(fake_storage, stub_inspect):
    doc = inspecting(fake_storage)
    QuotaUsage.objects.filter(pk=ALICE).update(bytes_used=500 * MB)
    assert jobs_pdf.inspect_job({"document_id": str(doc.id)})["status"] == "ready"
    assert Document.objects.get(pk=doc.pk).cover_attachment_id is None and Attachment.objects.count() == 1


# --- extract ------------------------------------------------------------------------------------------------------------------
def pending_content(fake_storage, pages=45, **fields):
    content = make_content(page_count=pages, text_status="pending", **fields)
    attachment = make_attachment(ALICE)
    fake_storage.upload(attachment.bucket, attachment.path, DATA, content_type="application/pdf", cache_control="")
    doc = make_document(ALICE, attachment=attachment, content=content, status="ready", page_count=pages)
    return content, doc


@pytest.fixture
def stub_extract(monkeypatch):
    calls = []

    def fake(path, page_from, page_to, **kwargs):
        calls.append((page_from, page_to))
        return [
            worker_extract.PageText(n, f"page {n} text about input credit", 30, "en")
            for n in range(page_from, page_to + 1)
        ]

    monkeypatch.setattr(worker_extract, "extract_pages", fake)
    return calls


def test_extraction_runs_in_chunks_of_twenty_and_finishes_done(fake_storage, stub_extract, capture_events):
    ready = capture_events("notes_document_ready")
    content, doc = pending_content(fake_storage)
    out = jobs_pdf.extract_text_job({"content_id": str(content.pk), "document_id": str(doc.id)})
    assert out == {"done": True, "pages": 45, "unreadable_pages": 0} and stub_extract == [(1, 20), (21, 40), (41, 45)]
    content.refresh_from_db()
    assert (content.text_status, content.text_pages_done) == ("done", 45) and FilePage.objects.filter(
        content=content
    ).count() == 45
    assert FilePage.objects.get(content=content, page=7).lang == "en"
    assert [e["stage"] for e in ready] == ["searchable"] and ready[0]["pages"] == 45
    assert jobs_pdf.extract_text_job({"content_id": str(content.pk)}) == {"skipped": "done"}


def test_a_long_file_is_continued_as_a_new_job_from_the_page_it_reached(fake_storage, stub_extract, monkeypatch):
    monkeypatch.setattr(jobs_pdf, "EXTRACT_BUDGET_SECONDS", -1)  # the budget is spent after the first chunk
    content, doc = pending_content(fake_storage)
    out = jobs_pdf.extract_text_job({"content_id": str(content.pk), "document_id": str(doc.id)})
    assert out == {"chained": 21} and stub_extract == [(1, 20)]
    content.refresh_from_db()
    assert (content.text_status, content.text_pages_done) == ("running", 20)
    nxt = Job.objects.get(type="notes.extract_text", dedupe_key=f"notes.extract_text:{content.pk}:21")
    assert nxt.payload["from"] == 21
    assert jobs_pdf.extract_text_job(nxt.payload) == {"chained": 41}  # and so on, until the end
    assert jobs_pdf.extract_text_job({"content_id": str(content.pk), "from": 41})["done"] is True


def test_a_restarted_job_resumes_after_the_last_page_done(fake_storage, stub_extract):
    content, doc = pending_content(fake_storage, text_pages_done=20)
    jobs_pdf.extract_text_job({"content_id": str(content.pk), "document_id": str(doc.id)})
    assert stub_extract[0] == (21, 40)


def test_the_heartbeat_runs_between_chunks(fake_storage, stub_extract, monkeypatch):
    beats = []
    monkeypatch.setattr(jobs_pdf.core_jobs, "heartbeat", lambda job=None: beats.append(1) or True)
    content, doc = pending_content(fake_storage)
    jobs_pdf.extract_text_job({"content_id": str(content.pk), "document_id": str(doc.id)})
    assert len(beats) == 3


def test_a_lost_lock_stops_the_job_without_finishing(fake_storage, stub_extract, monkeypatch):
    monkeypatch.setattr(jobs_pdf.core_jobs, "heartbeat", lambda job=None: False)
    monkeypatch.setattr(jobs_pdf.core_jobs, "current_job", lambda: object())
    content, doc = pending_content(fake_storage)
    assert jobs_pdf.extract_text_job({"content_id": str(content.pk), "document_id": str(doc.id)}) == {
        "stopped": "lock lost",
        "reached": 20,
    }
    assert FileContent.objects.get(pk=content.pk).text_status == "running"


def test_text_of_a_higher_rank_is_never_replaced_by_a_native_rerun(fake_storage, stub_extract):
    content, doc = pending_content(fake_storage, pages=3)
    FilePage.objects.create(content=content, page=2, text="ocr text of page two", text_source="ocr", ocr_conf=88)
    jobs_pdf.extract_text_job({"content_id": str(content.pk), "document_id": str(doc.id)})
    kept = FilePage.objects.get(content=content, page=2)
    assert (kept.text, kept.text_source, kept.ocr_conf) == ("ocr text of page two", "ocr", 88)
    assert FilePage.objects.get(content=content, page=1).text_source == "native"
    FileContent.objects.filter(pk=content.pk).update(text_status="pending", text_pages_done=0)
    jobs_pdf.extract_text_job({"content_id": str(content.pk)})  # a re-extraction (reextract_content) is safe too
    assert FilePage.objects.get(content=content, page=2).text_source == "ocr"


def test_text_pages_done_only_ever_grows(fake_storage, stub_extract):
    content, doc = pending_content(fake_storage, pages=40)
    FileContent.objects.filter(pk=content.pk).update(text_pages_done=39)
    jobs_pdf.extract_text_job({"content_id": str(content.pk), "document_id": str(doc.id), "from": 1})
    assert FileContent.objects.get(pk=content.pk).text_pages_done == 40
    from modules.notes.services import file_pages

    file_pages.record_text_progress(content.pk, 5)
    assert FileContent.objects.get(pk=content.pk).text_pages_done == 40


def test_a_password_protected_content_is_locked_not_failed(fake_storage, monkeypatch):
    monkeypatch.setattr(worker_extract, "extract_pages", lambda *a, **k: (_ for _ in ()).throw(PdfPasswordRequired()))
    content, doc = pending_content(fake_storage)
    assert jobs_pdf.extract_text_job({"content_id": str(content.pk), "document_id": str(doc.id)}) == {"locked": True}
    assert FileContent.objects.get(pk=content.pk).text_status == "locked"
    encrypted = make_content(is_encrypted=True, text_status="pending")  # no page count: never readable by the worker
    assert jobs_pdf.extract_text_job({"content_id": str(encrypted.pk)}) == {"skipped": "locked"}
    assert FileContent.objects.get(pk=encrypted.pk).text_status == "locked"


def test_an_unreadable_file_marks_the_text_failed(fake_storage, monkeypatch):
    monkeypatch.setattr(worker_extract, "extract_pages", lambda *a, **k: (_ for _ in ()).throw(PdfOpenError("broken")))
    content, doc = pending_content(fake_storage)
    assert jobs_pdf.extract_text_job({"content_id": str(content.pk), "document_id": str(doc.id)}) == {
        "failed": "unreadable"
    }
    assert FileContent.objects.get(pk=content.pk).text_status == "failed"


def test_without_any_document_left_the_job_does_nothing(fake_storage, stub_extract):
    content = make_content(page_count=5, text_status="pending")
    assert jobs_pdf.extract_text_job({"content_id": str(content.pk)}) == {"skipped": "no_document"}
    assert jobs_pdf.extract_text_job({"content_id": str(uuid.uuid4())}) == {"skipped": "gone"}


def test_scanned_content_does_not_announce_searchable_when_ocr_is_wanted(fake_storage, stub_extract, capture_events):
    ready = capture_events("notes_document_ready")
    content, doc = pending_content(fake_storage, pages=2, is_scanned=True, ocr_status="running")
    jobs_pdf.extract_text_job({"content_id": str(content.pk), "document_id": str(doc.id)})
    assert ready == []


def test_the_handlers_are_registered_and_the_heavy_ones_stay_with_the_worker():
    from modules.notes import jobs as notes_jobs

    assert {"notes.inspect", "notes.extract_text", "notes.expire_reservations"} <= set(jobs.handler_types())
    assert "notes.expire_reservations" in notes_jobs.LIGHT_TYPES
    assert {"notes.inspect", "notes.extract_text"} <= set(notes_jobs.HEAVY_TYPES)
