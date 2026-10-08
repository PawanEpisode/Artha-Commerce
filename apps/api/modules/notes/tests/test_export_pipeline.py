"""The flattened export job end to end: fake storage, the real export library on generated PDFs, marks of every kind."""
# ruff: noqa: F811 - pytest fixtures imported from `ocr_export_support` are redefined as test arguments

import hashlib
import io
import uuid
from datetime import timedelta

import pikepdf
import pytest
from django.utils import timezone

from core import events as bus
from core import jobs
from core.models import Job
from modules.coverage.tests.conftest import OTHER, USER
from modules.media.models import Attachment
from modules.notes import events
from modules.notes.domain.export_options import validate_options
from modules.notes.models import ExportJob, FileContent, ItemTag, MonthlyUsage
from modules.notes.selectors import exports as export_selectors
from modules.notes.services import exports
from modules.notes.worker import export as engine

from .factories import make_annotation, make_tag
from .ocr_export_support import fake_storage, make_pdf_document, run_jobs  # noqa: F401
from .test_export_request import exports_used, post
from .worker.conftest import fonts_dir  # noqa: F401
from .worker.fixtures import make_pdfs as mk

pytestmark = pytest.mark.django_db
TYPES = ["notes.export_pdf"]
QUADS = {"quads": [[0.1, 0.1, 0.4, 0.02]]}
ALL_KINDS = (
    ("highlight", "y", "", QUADS),
    ("underline", "g", "", QUADS),
    ("ink", "i2", "", {"strokes": [{"pts": [[0.1, 0.5], [0.4, 0.55]], "w": 0.004}]}),
    ("area", "b", "", {"rect": [0.5, 0.5, 0.2, 0.1]}),
    ("sticky", "o", "check this", {"pt": [0.8, 0.1]}),
    ("textbox", "y", "Remember Section 17(5)", {"rect": [0.1, 0.7, 0.5, 0.06], "fs": 0.018}),
)


@pytest.fixture(autouse=True)
def _fonts(fonts_dir, monkeypatch):
    monkeypatch.setenv("WORKER_FONTS_DIR", str(fonts_dir))


@pytest.fixture
def doc(fake_storage, tmp_path):
    return make_pdf_document(
        fake_storage, USER, mk.text_pdf(tmp_path / "t.pdf", pages=3), can_copy=True, can_modify=True
    )


def marked(doc, page=1, **fields):
    return make_annotation(doc, page=page, **fields)


def add_all_kinds(doc):
    for page, (kind, color, comment, geometry) in enumerate(ALL_KINDS, start=1):
        marked(doc, page=(page - 1) % 3 + 1, kind=kind, color=color, comment=comment, geometry=geometry)


def stored(fake, attachment) -> bytes:
    return fake.objects[(attachment.bucket, attachment.path)]


def fetch(api, job_id):
    return api.get(f"/notes/exports/{job_id}/").json_body


def test_a_pdf_with_marks_of_every_kind_is_built_stored_and_signed_on_demand(api, doc, fake_storage):
    add_all_kinds(doc)
    original = stored(fake_storage, doc.attachment)
    seen = []
    listener = lambda **p: seen.append(p)  # noqa: E731
    bus.subscribe(events.NOTES_EXPORT_READY, listener)
    try:
        job = post(api, doc).json_body["export"]
        assert run_jobs(TYPES) == 1
    finally:
        bus._subscribers[events.NOTES_EXPORT_READY].remove(listener)
    done = fetch(api, job["id"])
    assert (done["status"], done["progress"], done["page_count"], done["error_code"]) == ("done", 100, 3, None)
    assert done["download_url"].startswith("https://") and "/exports/" in done["download_url"]
    expires = timezone.datetime.fromisoformat(done["expires_at"])
    assert timedelta(days=6, hours=23) < expires - timezone.now() <= timedelta(days=7)
    row = ExportJob.objects.get(pk=job["id"])
    attachment = row.attachment
    assert attachment.kind == "note_export" and attachment.status == "clean" and attachment.mime == "application/pdf"
    assert attachment.path == f"{USER}/exports/{attachment.id}.pdf"  # ids only: no title, no file name
    out = stored(fake_storage, attachment)
    with pikepdf.open(io.BytesIO(out)) as pdf:
        assert len(pdf.pages) == 3
    assert attachment.bytes == len(out)
    # the ORIGINAL is the same object, byte for byte, in storage and in the row
    assert hashlib.sha256(stored(fake_storage, doc.attachment)).hexdigest() == hashlib.sha256(original).hexdigest()
    assert out != original
    assert seen == [
        {"user_id": str(USER), "export_id": job["id"], "kind": "pdf", "document_id": str(doc.id), "page_count": 3}
    ]
    assert exports_used() == 1  # a finished export keeps its charge


def test_the_options_page_range_kinds_and_appendix_shape_the_output(api, doc, fake_storage):
    add_all_kinds(doc)
    job = post(api, doc, options={"pages": "2-3", "include": ["sticky"], "appendix": True}).json_body["export"]
    run_jobs(TYPES)
    done = fetch(api, job["id"])
    assert (
        done["status"] == "done" and done["page_count"] == 3
    )  # two pages and one appendix page of the sticky's comment
    with pikepdf.open(io.BytesIO(stored(fake_storage, ExportJob.objects.get(pk=job["id"]).attachment))) as pdf:
        assert len(pdf.pages) == 3


def test_marks_are_filtered_by_kind_page_colour_and_tag_in_one_ordered_pass(doc, django_assert_num_queries):
    other = make_pdf_document  # noqa: F841 - readability: the second document must never leak in
    yellow = marked(doc, page=2, kind="highlight", color="y", geometry=QUADS)
    green = marked(doc, page=1, kind="highlight", color="g", geometry=QUADS)
    ink = marked(doc, page=1, kind="ink", color="i2", geometry={"strokes": []})
    plain = marked(doc, page=3, kind="textbox", color=None, comment="no colour", geometry={"rect": [0, 0, 1, 1]})
    gone = marked(doc, page=1, kind="highlight", color="y", geometry=QUADS, deleted_at=timezone.now())
    marked(doc, page=1, kind="bookmark", color=None, geometry={"y": 0.2})
    tag = make_tag(USER, "revise")
    ItemTag.objects.create(user_id=USER, tag=tag, annotation=green)
    del yellow, ink, plain, gone

    def pick(**opts):
        options = validate_options(opts, 3)
        return [(m["page"], m["kind"], m["color"]) for m in export_selectors.marks_for_export(USER, doc.id, options)]

    with django_assert_num_queries(1):
        everything = pick()
    assert everything == [
        (1, "highlight", "g"),
        (1, "ink", "i2"),
        (2, "highlight", "y"),
        (3, "textbox", None),
    ]  # no tombstone, no bookmark
    assert pick(include=["highlight"]) == [(1, "highlight", "g"), (2, "highlight", "y")]
    assert pick(pages="2-3") == [(2, "highlight", "y"), (3, "textbox", None)]
    assert pick(colors=["g"]) == [
        (1, "highlight", "g"),
        (3, "textbox", None),
    ]  # a mark without a colour has none to filter
    assert pick(tags=[str(tag.id)]) == [(1, "highlight", "g")]
    assert pick(tags=[str(uuid.uuid4())]) == []
    assert export_selectors.marks_for_export(OTHER, doc.id, validate_options({}, 3)) == []


def test_a_file_the_library_calls_restricted_fails_the_job_and_refunds(api, fake_storage, tmp_path):
    path = mk.owner_only_pdf(tmp_path / "owner.pdf", mk.text_pdf(tmp_path / "src.pdf"))
    doc = make_pdf_document(fake_storage, USER, path, can_copy=None, can_modify=None)  # flags unknown: the file decides
    job = post(api, doc).json_body["export"]
    assert exports_used() == 1
    run_jobs(TYPES)
    done = fetch(api, job["id"])
    assert (done["status"], done["error_code"], done["download_url"]) == ("failed", "restricted", None)
    assert exports_used() == 0 and not Attachment.objects.filter(kind="note_export").exists()


def test_a_file_that_needs_a_password_fails_as_locked(api, fake_storage, tmp_path):
    path = mk.encrypted_pdf(tmp_path / "locked.pdf", mk.text_pdf(tmp_path / "src.pdf"))
    doc = make_pdf_document(fake_storage, USER, path, can_copy=None, can_modify=None, page_count=3)
    job = post(api, doc).json_body["export"]
    run_jobs(TYPES)
    done = fetch(api, job["id"])
    assert (done["status"], done["error_code"]) == ("failed", "locked") and exports_used() == 0


def test_a_document_that_turned_restricted_after_queueing_fails_without_building(api, doc):
    job = post(api, doc).json_body["export"]
    FileContent.objects.filter(pk=doc.content_id).update(can_copy=False)
    run_jobs(TYPES)
    assert fetch(api, job["id"])["error_code"] == "restricted" and exports_used() == 0


def test_too_large_fails_with_a_page_range_suggestion_in_the_details(api, doc, monkeypatch):
    def too_big(*args, **kwargs):
        raise engine.ExportTooLarge("slow", (1, 640))

    monkeypatch.setattr(engine, "build_flattened_pdf", too_big)
    job = post(api, doc, options={"pages": "1-2"}).json_body["export"]
    run_jobs(TYPES)
    done = fetch(api, job["id"])
    assert (done["status"], done["error_code"]) == ("failed", "export_too_large")
    assert done["details"] == {"suggested_pages": "1-640"}
    assert done["options"] == {"pages": "1-2"}  # the hint is not an option
    assert exports_used() == 0


def test_a_real_page_limit_is_reported_too_large(api, fake_storage, tmp_path, monkeypatch):
    from modules.notes.worker import pdfutil

    monkeypatch.setattr(pdfutil, "MAX_PAGES", 2)
    doc = make_pdf_document(
        fake_storage, USER, mk.text_pdf(tmp_path / "t.pdf", pages=5), can_copy=True, can_modify=True
    )
    job = post(api, doc).json_body["export"]
    run_jobs(TYPES)
    done = fetch(api, job["id"])
    assert (done["error_code"], done["details"]) == ("export_too_large", {"suggested_pages": "1-2"})


def test_an_unexpected_error_retries_and_the_last_attempt_fails_the_job_and_refunds(api, doc, monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("disk full")

    monkeypatch.setattr(engine, "build_flattened_pdf", boom)
    job = post(api, doc).json_body["export"]
    for _ in range(5):
        Job.objects.filter(status="queued").update(run_after=timezone.now())
        run_jobs(TYPES, limit=1)
        if _ < 4:
            assert fetch(api, job["id"])["status"] == "running"  # between attempts it is still in progress
    queue_row = Job.objects.get(type="notes.export_pdf")
    assert queue_row.status == "failed" and queue_row.attempts == 5
    done = fetch(api, job["id"])
    assert (done["status"], done["error_code"]) == ("failed", "failed") and exports_used() == 0


def test_a_missing_original_retries_instead_of_failing_the_student(api, doc, fake_storage):
    job = post(api, doc).json_body["export"]
    fake_storage.objects.clear()
    run_jobs(TYPES, limit=1)
    assert Job.objects.get(type="notes.export_pdf").status == "queued"
    assert fetch(api, job["id"])["status"] == "running"


def test_a_finished_job_is_not_run_twice(api, doc, fake_storage):
    job = post(api, doc).json_body["export"]
    run_jobs(TYPES)
    first = ExportJob.objects.get(pk=job["id"]).attachment_id
    jobs.enqueue("notes.export_pdf", {"export_id": job["id"]}, dedupe_key="replay")
    run_jobs(TYPES)
    assert ExportJob.objects.get(pk=job["id"]).attachment_id == first
    assert Attachment.objects.filter(kind="note_export").count() == 1


def test_a_job_that_was_failed_while_building_discards_its_file(api, doc, monkeypatch):
    job = post(api, doc).json_body["export"]
    real = engine.build_flattened_pdf

    def racing(*args, **kwargs):
        result = real(*args, **kwargs)
        ExportJob.objects.filter(pk=job["id"]).update(status="failed", error_code="failed")
        return result

    monkeypatch.setattr(engine, "build_flattened_pdf", racing)
    run_jobs(TYPES)
    assert ExportJob.objects.get(pk=job["id"]).status == "failed"
    assert Attachment.objects.get(kind="note_export").status == "deleting"


def test_the_signed_link_is_issued_on_demand_and_never_for_anyone_else(api, other_api, doc):
    job = post(api, doc).json_body["export"]
    assert fetch(api, job["id"])["download_url"] is None  # not before it is done
    run_jobs(TYPES)
    assert fetch(api, job["id"])["download_url"]
    assert other_api.get(f"/notes/exports/{job['id']}/").status_code == 404


def test_exports_expire_after_seven_days_and_their_files_are_queued_for_deletion(api, doc, fake_storage):
    job = post(api, doc).json_body["export"]
    run_jobs(TYPES)
    row = ExportJob.objects.get(pk=job["id"])
    attachment_id = row.attachment_id
    assert exports.expire_exports() == {"expired": 0, "removed": 0}  # a fresh export stays
    ExportJob.objects.filter(pk=row.pk).update(expires_at=timezone.now() - timedelta(minutes=1))
    gone = fetch(api, job["id"])
    assert gone["status"] == "expired" and gone["download_url"] is None  # expired before the sweep has even run
    assert exports.expire_exports() == {"expired": 1, "removed": 0}
    assert ExportJob.objects.get(pk=row.pk).status == "expired"
    assert Attachment.objects.get(pk=attachment_id).status == "deleting"
    assert Job.objects.filter(type="media.delete", payload={"attachment_id": str(attachment_id)}).exists()
    run_jobs(["media.delete"])
    assert not Attachment.objects.filter(pk=attachment_id).exists()
    assert ExportJob.objects.get(pk=row.pk).attachment_id is None and fetch(api, job["id"])["status"] == "expired"
    assert exports.expire_exports() == {"expired": 0, "removed": 0}  # idempotent
    ExportJob.objects.filter(pk=row.pk).update(created_at=timezone.now() - timedelta(days=15))
    assert exports.expire_exports()["removed"] == 1 and not ExportJob.objects.filter(pk=row.pk).exists()
    assert not fake_storage.objects.get((doc.attachment.bucket, f"{USER}/exports/{attachment_id}.pdf"))


def test_the_expiry_job_runs_in_the_tick_and_not_in_the_worker(api, doc):
    from modules.notes import jobs as notes_jobs

    assert notes_jobs.JOB_EXPIRE_EXPORTS in notes_jobs.LIGHT_TYPES
    assert notes_jobs.JOB_EXPIRE_EXPORTS not in notes_jobs.HEAVY_TYPES
    job = post(api, doc).json_body["export"]
    run_jobs(TYPES)
    ExportJob.objects.filter(pk=job["id"]).update(expires_at=timezone.now() - timedelta(hours=1))
    notes_jobs.tick()
    assert ExportJob.objects.get(pk=job["id"]).status == "expired"
    assert MonthlyUsage.objects.get(user_id=USER).exports == 1  # expiry gives nothing back: the export was delivered
