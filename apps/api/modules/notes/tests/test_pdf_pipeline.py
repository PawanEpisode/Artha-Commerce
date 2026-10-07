"""
The whole PDF pipeline with the real worker libraries on generated PDFs and a fake object store: reserve, PUT, complete, scan (the
null scanner), inspect, extract, and what the library, the reading endpoints and the searches show at each point.
"""

import hashlib

import pytest

from core import jobs
from core.models import Job
from modules.media.models import Attachment
from modules.notes.models import Document, FileContent, FilePage, QuotaUsage

from .documents_support import HEAVY, make_pdf, run_worker, upload_and_complete
from .factories import ALICE

pytestmark = pytest.mark.django_db


def library(api):
    return {d["id"]: d for d in api.get("/notes/documents/").json_body["items"]}


def test_a_text_pdf_goes_from_reserved_to_searchable(
    api, fake_storage, tmp_path, django_capture_on_commit_callbacks, capture_events
):
    ready = capture_events("notes_document_ready")
    data = make_pdf(tmp_path, "text", pages=3)
    doc = upload_and_complete(api, fake_storage, data, django_capture_on_commit_callbacks)
    assert doc["status"] == "inspecting" and doc["text_status"] == "pending" and doc["can_open"] is True
    assert Job.objects.filter(type="notes.inspect", status="queued").count() == 1  # the on_clean hook queued it
    assert Document.objects.get(pk=doc["id"]).content_id is None
    assert run_worker() == 2  # inspect, then extract
    shown = api.get(f"/notes/documents/{doc['id']}/").json_body
    assert shown["status"] == "ready" and shown["page_count"] == 3 and shown["is_scanned"] is False
    assert shown["text_status"] == "done" and shown["text_pages_done"] == 3
    assert len(shown["page_meta"]) == 3 and shown["page_meta"][0]["w"] > 500 and shown["is_encrypted"] is False
    assert shown["can_copy"] is True and shown["has_javascript"] is False and shown["cover_url"]
    content = FileContent.objects.get()
    assert content.sha256 == hashlib.sha256(data).hexdigest() and content.bytes == len(data)
    assert FilePage.objects.filter(content=content).count() == 3
    assert [(e["stage"], e["pages"], e["scanned"], e["encrypted"]) for e in ready] == [
        ("readable", 3, False, False),
        ("searchable", 3, False, False),
    ]
    cover = Attachment.objects.get(pk=Document.objects.get().cover_attachment_id)
    assert cover.kind == "note_image" and cover.status == "clean" and cover.mime == "image/webp"
    assert fake_storage.objects[(cover.bucket, cover.path)][:4] == b"RIFF"
    usage = QuotaUsage.objects.get(pk=ALICE)
    assert usage.docs_active == 1 and usage.bytes_used == len(data) + cover.bytes
    assert (
        shown["file_url"]
        and fake_storage.objects[(Document.objects.get().attachment.bucket, Document.objects.get().attachment.path)]
        == data
    )


def test_the_reading_endpoints_follow_the_pipeline(api, fake_storage, tmp_path, django_capture_on_commit_callbacks):
    doc = upload_and_complete(
        api, fake_storage, make_pdf(tmp_path, "text", pages=25), django_capture_on_commit_callbacks
    )
    early = api.get(f"/notes/documents/{doc['id']}/processing/").json_body
    assert early["status"] == "inspecting" and early["text_status"] == "pending" and early["page_count"] is None
    assert api.get(f"/notes/documents/{doc['id']}/pages/text/?from=1&to=3").json_body["pages"] == []
    assert api.get(f"/notes/documents/{doc['id']}/search/?q=credit").json_body["indexed_pages"] == 0
    run_worker()
    done = api.get(f"/notes/documents/{doc['id']}/processing/").json_body
    assert done == {
        "status": "ready",
        "status_reason": None,
        "text_status": "done",
        "text_pages_done": 25,
        "ocr_status": "none",
        "ocr_pages_done": 0,
        "ocr_pages_total": 0,
        "page_count": 25,
        "is_scanned": False,
    }
    text = api.get(f"/notes/documents/{doc['id']}/pages/text/?from=24&to=25").json_body
    assert [p["page"] for p in text["pages"]] == [24, 25] and "Input tax credit" in text["pages"][0]["text"]
    assert (
        text["pages"][0]["source"] == "native" and text["pages"][0]["words"] is None and text["text_status"] == "done"
    )
    assert api.get(f"/notes/documents/{doc['id']}/pages/text/?from=1&to=21").status_code == 400  # at most 20 pages
    assert (
        len(api.get(f"/notes/documents/{doc['id']}/pages/text/?from=1").json_body["pages"]) == 20
    )  # the default window
    hits = api.get(f"/notes/documents/{doc['id']}/search/?q=credit").json_body
    assert hits["indexed_pages"] == 25 and hits["page_count"] == 25 and len(hits["items"]) == 25
    assert {"page", "snippet", "rank"} <= set(hits["items"][0]) and "credit" in hits["items"][0]["snippet"].lower()
    assert api.get(f"/notes/documents/{doc['id']}/search/?q=zzzunseen").json_body["items"] == []


def test_a_scanned_pdf_is_ready_but_not_searchable_until_ocr(
    api, fake_storage, tmp_path, django_capture_on_commit_callbacks, capture_events
):
    ready = capture_events("notes_document_ready")
    doc = upload_and_complete(
        api, fake_storage, make_pdf(tmp_path, "scanned", pages=2), django_capture_on_commit_callbacks
    )
    run_worker()
    shown = api.get(f"/notes/documents/{doc['id']}/").json_body
    assert shown["status"] == "ready" and shown["is_scanned"] is True and shown["text_status"] == "done"
    assert all(
        p["text"] == "" for p in api.get(f"/notes/documents/{doc['id']}/pages/text/?from=1&to=2").json_body["pages"]
    )
    found = api.get("/notes/search/?q=credit&scope=pdf").json_body
    assert found["items"] == [] and found["meta"]["not_searchable"] == [{"document_id": doc["id"], "reason": "scanned"}]
    assert [e["stage"] for e in ready] == [
        "readable",
        "searchable",
    ]  # OCR was not asked for, so the text pass is the end


def test_an_encrypted_pdf_needs_its_password_and_reads_in_the_browser(
    api, fake_storage, tmp_path, django_capture_on_commit_callbacks
):
    doc = upload_and_complete(api, fake_storage, make_pdf(tmp_path, "encrypted"), django_capture_on_commit_callbacks)
    assert run_worker() == 1  # inspect only: nothing to extract without the password
    shown = api.get(f"/notes/documents/{doc['id']}/").json_body
    assert shown["status"] == "needs_password" and shown["is_encrypted"] is True and shown["file_url"]
    assert shown["text_status"] == "locked" and shown["page_meta"] is None
    assert not FilePage.objects.exists()
    found = api.get("/notes/search/?q=credit&scope=pdf").json_body
    assert found["meta"]["not_searchable"] == [{"document_id": doc["id"], "reason": "locked"}]


def test_a_damaged_pdf_is_rejected_and_gives_its_quota_back(
    api, fake_storage, tmp_path, django_capture_on_commit_callbacks
):
    data = make_pdf(tmp_path, "corrupt", pages=6)
    doc = upload_and_complete(api, fake_storage, data, django_capture_on_commit_callbacks)
    run_worker()
    shown = api.get(f"/notes/documents/{doc['id']}/").json_body
    assert shown["status"] == "rejected" and shown["status_reason"] in ("pdf_corrupt", "decode_failed")
    assert shown["file_url"] is None and shown["can_open"] is False
    usage = QuotaUsage.objects.get(pk=ALICE)
    assert (usage.bytes_used, usage.docs_active) == (0, 0)
    attachment = Document.objects.get().attachment
    assert attachment.status == "rejected" and attachment.bytes == 0 and not fake_storage.objects
    assert api.delete(f"/notes/documents/{doc['id']}/?permanent=1").status_code == 200
    assert (QuotaUsage.objects.get(pk=ALICE).bytes_used, QuotaUsage.objects.get(pk=ALICE).docs_active) == (0, 0)


def test_the_library_shows_the_right_status_for_each_kind_of_file(
    api, fake_storage, tmp_path, django_capture_on_commit_callbacks
):
    kinds = {
        kind: upload_and_complete(api, fake_storage, make_pdf(tmp_path, kind), django_capture_on_commit_callbacks)["id"]
        for kind in ("text", "scanned", "encrypted", "corrupt")
    }
    assert {d["status"] for d in library(api).values()} == {"inspecting"}
    run_worker()
    got = {kind: library(api)[doc_id]["status"] for kind, doc_id in kinds.items()}
    assert got == {"text": "ready", "scanned": "ready", "encrypted": "needs_password", "corrupt": "rejected"}
    assert [d["id"] for d in api.get("/notes/documents/?status=ready&limit=3").json_body["items"]] and len(
        api.get("/notes/documents/?status=ready").json_body["items"]
    ) == 2


def test_inspection_is_idempotent_and_a_replayed_job_changes_nothing(
    api, fake_storage, tmp_path, django_capture_on_commit_callbacks
):
    from modules.notes import jobs_pdf

    doc = upload_and_complete(api, fake_storage, make_pdf(tmp_path, "text"), django_capture_on_commit_callbacks)
    run_worker()
    before = (FileContent.objects.count(), FilePage.objects.count(), Attachment.objects.count())
    assert jobs_pdf.inspect_job({"document_id": doc["id"]}) == {"skipped": "ready"}
    assert jobs_pdf.extract_text_job({"content_id": str(FileContent.objects.get().pk)}) == {"skipped": "done"}
    assert (FileContent.objects.count(), FilePage.objects.count(), Attachment.objects.count()) == before


def test_a_second_student_with_identical_bytes_reuses_the_derived_text_and_sees_only_their_own(
    api, other_api, fake_storage, tmp_path, django_capture_on_commit_callbacks, capture_events
):
    ready = capture_events("notes_document_ready")
    data = make_pdf(tmp_path, "text", pages=4)
    mine = upload_and_complete(api, fake_storage, data, django_capture_on_commit_callbacks)
    run_worker()
    pages_before = FilePage.objects.count()
    theirs = upload_and_complete(other_api, fake_storage, data, django_capture_on_commit_callbacks)
    assert run_worker() == 1  # inspect only: the text is already there
    assert FileContent.objects.count() == 1 and FilePage.objects.count() == pages_before == 4
    assert Document.objects.get(pk=mine["id"]).content_id == Document.objects.get(pk=theirs["id"]).content_id
    shown = other_api.get(f"/notes/documents/{theirs['id']}/").json_body
    assert shown["status"] == "ready" and shown["text_status"] == "done" and shown["page_count"] == 4
    assert [(e["document_id"] == theirs["id"], e["stage"]) for e in ready][-2:] == [
        (True, "readable"),
        (True, "searchable"),
    ]
    # each sees only their own document in every search, though the pages are shared
    mine_found = api.get("/notes/search/?q=credit&scope=pdf").json_body["items"]
    theirs_found = other_api.get("/notes/search/?q=credit&scope=pdf").json_body["items"]
    assert {h["document_id"] for h in mine_found} == {mine["id"]} and {h["document_id"] for h in theirs_found} == {
        theirs["id"]
    }
    assert other_api.get(f"/notes/documents/{mine['id']}/search/?q=credit").status_code == 404
    assert other_api.get(f"/notes/documents/{mine['id']}/pages/text/?from=1&to=2").status_code == 404
    # the first student deleting theirs does not take the text away from the second
    api.delete(f"/notes/documents/{mine['id']}/?permanent=1")
    assert FileContent.objects.get().orphaned_at is None and FilePage.objects.count() == 4
    assert len(other_api.get("/notes/search/?q=credit&scope=pdf").json_body["items"]) == 4


def test_a_reupload_of_orphaned_content_adopts_it_again(
    api, fake_storage, tmp_path, django_capture_on_commit_callbacks
):
    data = make_pdf(tmp_path, "text", pages=2)
    first = upload_and_complete(api, fake_storage, data, django_capture_on_commit_callbacks)
    run_worker()
    api.delete(f"/notes/documents/{first['id']}/?permanent=1")
    assert FileContent.objects.get().orphaned_at is not None
    again = upload_and_complete(api, fake_storage, data, django_capture_on_commit_callbacks)
    run_worker()
    assert FileContent.objects.get().orphaned_at is None
    assert (
        api.get(f"/notes/documents/{again['id']}/").json_body["text_status"] == "done" and FilePage.objects.count() == 2
    )


def test_the_original_bytes_never_change_through_the_pipeline(
    api, fake_storage, tmp_path, django_capture_on_commit_callbacks
):
    data = make_pdf(tmp_path, "text")
    doc = upload_and_complete(api, fake_storage, data, django_capture_on_commit_callbacks)
    attachment = Document.objects.get(pk=doc["id"]).attachment
    run_worker()
    api.patch(f"/notes/documents/{doc['id']}/", {"title": "Renamed"})
    assert fake_storage.objects[(attachment.bucket, attachment.path)] == data
    assert (
        hashlib.sha256(fake_storage.objects[(attachment.bucket, attachment.path)]).hexdigest()
        == FileContent.objects.get().sha256
    )
    assert not jobs.claim_next(types=HEAVY)
