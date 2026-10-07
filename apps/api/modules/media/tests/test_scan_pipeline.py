"""Content sniffing at completion, the scan job, rejection and its quota, for the `note_pdf` and `note_image` kinds."""

import uuid

import pytest

from core import jobs
from modules.media import registry, scanner, services
from modules.media.models import Attachment
from modules.notes.models import Document, QuotaUsage

from .conftest import upload_image

pytestmark = pytest.mark.django_db

USER = uuid.UUID("3f2b8c7e-6d2e-4f0e-9a45-0f9e5b3e1c11")
PDF = b"%PDF-1.7\n" + b"x" * 2000
MB = 1024 * 1024


class FakeScanner:
    inline = False

    def __init__(self, result=None, error=None):
        self.result, self.error, self.seen = result or scanner.ScanResult(clean=True), error, 0

    def scan(self, chunks):
        for chunk in chunks:
            self.seen += len(chunk)
        if self.error:
            raise self.error
        return self.result


@pytest.fixture(autouse=True)
def commit_at_once(monkeypatch):
    """Tests run inside one transaction, so `on_commit` callbacks would never fire: run them immediately instead."""
    monkeypatch.setattr("django.db.transaction.on_commit", lambda fn, **kw: fn())


@pytest.fixture
def real_scan(monkeypatch):
    """A scanner that is not the null one, so completion queues the scan job instead of marking the file clean."""
    fake = FakeScanner()
    monkeypatch.setattr("modules.media.scanner.get_scanner", lambda: fake)
    return fake


def reserve_pdf(fake_storage, data=PDF, size=None, put=True):
    upload = services.create_upload(USER, "note_pdf", mime="application/pdf", bytes=size or len(data))
    row = upload.attachment
    if put:
        fake_storage.upload(row.bucket, row.path, data, content_type="application/pdf", cache_control="")
    return row


def doc_for(attachment, status="scanning"):
    return Document.objects.create(
        user_id=USER, attachment=attachment, title="t", bytes=attachment.bytes, status=status
    )


def usage():
    return QuotaUsage.objects.get(pk=USER)


def test_a_pdf_lands_under_quarantine_with_ids_only_and_takes_a_document_slot(fake_storage):
    row = reserve_pdf(fake_storage, put=False)
    assert row.path == f"quarantine/{USER}/{row.id}.pdf" and row.bucket == "notes-private"
    assert (usage().bytes_used, usage().docs_active) == (len(PDF), 1)


def test_the_pdf_and_export_kinds_have_the_agreed_specs():
    pdf, export, image = (registry.get_kind(k) for k in ("note_pdf", "note_export", "note_image"))
    assert pdf.mimes == {"application/pdf"} and pdf.flag == "notes_pdf" and pdf.scan == "clamav" and not pdf.public
    assert pdf.max_bytes(str(USER)) == 50 * MB and pdf.sniff and pdf.on_clean and pdf.on_reject
    assert export.mimes == {"application/pdf", "application/zip"} and export.scan == "none" and not export.public
    assert export.retention_days == 7 and export.path_for("u", uuid.UUID(int=1), "application/zip").startswith(
        "u/exports/"
    )
    assert image.scan == "clamav" and image.public
    assert registry.public_kind_names() == ["note_image"]


def test_a_student_cannot_start_a_pdf_or_an_export_through_the_generic_endpoint(api, fake_storage):
    for kind, mime in (("note_pdf", "application/pdf"), ("note_export", "application/zip")):
        assert api.post("/media/uploads/", {"kind": kind, "mime": mime, "bytes": 100}).status_code == 400
    assert not Attachment.objects.exists()


def test_the_pdf_size_limit_is_the_plans_file_size(fake_storage):
    from modules.media.errors import FileTooLarge, UnsupportedType

    with pytest.raises(FileTooLarge):
        services.create_upload(USER, "note_pdf", mime="application/pdf", bytes=50 * MB + 1)
    with pytest.raises(UnsupportedType):
        services.create_upload(USER, "note_pdf", mime="image/png", bytes=10)
    assert not Attachment.objects.exists() and not QuotaUsage.objects.filter(bytes_used__gt=0).exists()


def test_with_the_null_scanner_a_good_pdf_is_clean_at_completion_and_queues_inspection(fake_storage):
    row = reserve_pdf(fake_storage)
    doc = doc_for(row)
    done = services.complete_upload(USER, row.id)
    assert done.status == "clean"
    doc.refresh_from_db()
    assert doc.status == "inspecting"
    job = jobs.claim_next(types=["notes.inspect"])
    assert job.payload == {"document_id": str(doc.id)}


def test_a_pdf_with_the_header_hidden_past_one_kilobyte_is_rejected_and_its_quota_returns(fake_storage):
    sneaky = b"PK\x03\x04" + b"\0" * 1100 + b"%PDF-1.7\n" + b"x" * 500
    row = reserve_pdf(fake_storage, sneaky)
    doc = doc_for(row)
    done = services.complete_upload(USER, row.id)
    assert (done.status, done.status_reason, done.bytes) == ("rejected", "type_mismatch", 0)
    assert (usage().bytes_used, usage().docs_active) == (0, 0)
    assert not fake_storage.objects  # the object is gone, not left in quarantine
    doc.refresh_from_db()
    assert (doc.status, doc.status_reason) == ("rejected", "type_mismatch")
    assert services.complete_upload(USER, row.id).status == "rejected"  # idempotent, nothing released twice
    assert (usage().bytes_used, usage().docs_active) == (0, 0)


def test_a_header_inside_the_first_kilobyte_is_accepted(fake_storage):
    for prefix in (b"", b"\n\n", b"junk" * 200):  # the spec tolerates leading junk up to 1 KB
        row = reserve_pdf(fake_storage, prefix + b"%PDF-2.0\n" + b"x" * 100)
        assert services.complete_upload(USER, row.id).status == "clean"


def test_a_real_scanner_leaves_the_file_uploaded_and_queues_the_scan_job(fake_storage, real_scan):
    row = reserve_pdf(fake_storage)
    assert services.complete_upload(USER, row.id).status == "uploaded"
    job = jobs.claim_next(types=["media.scan"])
    assert job.payload == {"attachment_id": str(row.id)}


def test_the_scan_job_marks_a_clean_file_clean_and_runs_on_clean(fake_storage, real_scan):
    row = reserve_pdf(fake_storage)
    doc = doc_for(row)
    services.complete_upload(USER, row.id)
    assert services.run_scan_job({"attachment_id": str(row.id)}) == {"scanned": True, "verdict": "clean"}
    again = services.run_scan_job({"attachment_id": str(row.id)})
    row.refresh_from_db(), doc.refresh_from_db()
    assert row.status == "clean" and doc.status == "inspecting" and again == {"scanned": False}
    assert real_scan.seen == len(PDF)


def test_the_scan_job_rejects_malware_deletes_the_object_and_releases_the_quota_once(fake_storage, real_scan):
    real_scan.result = scanner.ScanResult(clean=False, signature="Eicar-Test-Signature")
    row = reserve_pdf(fake_storage)
    doc = doc_for(row)
    services.complete_upload(USER, row.id)
    assert services.run_scan_job({"attachment_id": str(row.id)})["verdict"] == "malware"
    row.refresh_from_db(), doc.refresh_from_db()
    assert (row.status, row.status_reason, row.bytes) == ("rejected", "malware", 0)
    assert (doc.status, doc.status_reason) == ("rejected", "malware")
    assert not fake_storage.objects and (usage().bytes_used, usage().docs_active) == (0, 0)
    # removing the rejected row later (account erasure, purge of the document) must not release again
    other = reserve_pdf(fake_storage)  # a second, live document
    assert (usage().bytes_used, usage().docs_active) == (len(PDF), 1)
    doc.delete()
    services.queue_delete([row.id])
    services.run_delete_job({"attachment_id": str(row.id)})
    assert not Attachment.objects.filter(pk=row.id).exists()
    assert (usage().bytes_used, usage().docs_active) == (len(PDF), 1) and Attachment.objects.filter(
        pk=other.id
    ).exists()


def test_a_scanner_that_cannot_answer_retries_and_never_waves_the_file_through(fake_storage, real_scan):
    real_scan.error = scanner.ScannerError("clamd unreachable")
    row = reserve_pdf(fake_storage)
    services.complete_upload(USER, row.id)
    jobs.claim_next(types=["media.scan"])
    with pytest.raises(RuntimeError, match="Scan could not finish"):
        services.run_scan_job({"attachment_id": str(row.id)})
    row.refresh_from_db()
    assert row.status == "uploaded" and fake_storage.objects


def test_an_object_bigger_than_the_declared_size_is_rejected_too_large(fake_storage, real_scan):
    row = reserve_pdf(fake_storage, PDF, size=500)  # declared 500 bytes, uploaded 2,009
    services.complete_upload(USER, row.id)
    assert services.run_scan_job({"attachment_id": str(row.id)})["verdict"] == "too_large"
    row.refresh_from_db()
    assert (row.status, row.status_reason) == ("rejected", "too_large") and (
        usage().bytes_used,
        usage().docs_active,
    ) == (0, 0)


def test_images_follow_the_same_pipeline(api, fake_storage, real_scan):
    att = upload_image(api, fake_storage)
    assert api.post(f"/media/uploads/{att['id']}/complete/").json_body["attachment"]["status"] == "uploaded"
    services.run_scan_job({"attachment_id": att["id"]})
    assert Attachment.objects.get(pk=att["id"]).status == "clean"


def test_with_the_null_scanner_images_are_clean_at_completion(api, fake_storage):
    att = upload_image(api, fake_storage)
    assert api.post(f"/media/uploads/{att['id']}/complete/").json_body["attachment"]["status"] == "clean"


def test_a_storage_failure_while_rejecting_is_retried_not_swallowed(fake_storage):
    from modules.media.errors import StorageUnavailable

    row = reserve_pdf(fake_storage, b"not a pdf at all")
    fake_storage.fail_delete = True
    with pytest.raises(StorageUnavailable):
        services.complete_upload(USER, row.id)
    row.refresh_from_db()
    assert row.status == "reserved" and usage().docs_active == 1  # nothing half done
    fake_storage.fail_delete = False
    assert services.complete_upload(USER, row.id).status == "rejected"
