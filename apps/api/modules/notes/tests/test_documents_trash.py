"""Trash, restore and permanent delete: the quota arithmetic, the order of deletion and what is never touched."""

from datetime import timedelta

import pytest
from django.utils import timezone

from core import jobs
from modules.media.models import Attachment
from modules.notes.errors import QuotaExceeded
from modules.notes.models import Annotation, Document, ExportJob, FileContent, QuotaUsage
from modules.notes.services import document_trash

from .documents_support import MB, put_bytes, reserve
from .factories import ALICE, make_annotation, make_attachment, make_content, make_document, make_export

pytestmark = pytest.mark.django_db


def usage():
    row = QuotaUsage.objects.get(pk=ALICE)
    return row.bytes_used, row.docs_active


def uploaded(api, fake, size=4 * MB):
    doc = reserve(api, size).json_body["document"]
    put_bytes(fake, doc["id"], b"%PDF-1.4\n")
    Document.objects.filter(pk=doc["id"]).update(status="ready")
    return doc["id"]


def test_trash_keeps_counting_quota_and_restore_gives_it_back_unchanged(api, fake_storage):
    doc = uploaded(api, fake_storage)
    trashed = api.delete(f"/notes/documents/{doc}/")
    assert trashed.status_code == 200 and trashed.json_body["deleted_at"] and trashed.json_body["purge_after"]
    assert usage() == (4 * MB, 1)
    assert api.get("/notes/documents/").json_body["items"] == []
    assert [d["id"] for d in api.get("/notes/documents/?trashed=1").json_body["items"]] == [doc]
    again = api.delete(f"/notes/documents/{doc}/")  # idempotent: the first purge date stays
    assert again.json_body["purge_after"] == trashed.json_body["purge_after"]
    restored = api.post(f"/notes/documents/{doc}/restore/")
    assert restored.status_code == 200 and restored.json_body["deleted_at"] is None and restored.json_body["rev"] == 3
    assert usage() == (4 * MB, 1) and api.post(f"/notes/documents/{doc}/restore/").status_code == 200


def test_restore_refuses_a_student_who_is_over_a_limit_that_shrank(api, fake_storage):
    doc = uploaded(api, fake_storage)
    api.delete(f"/notes/documents/{doc}/")
    QuotaUsage.objects.filter(pk=ALICE).update(docs_active=101)  # the plan was cut after the trash
    res = api.post(f"/notes/documents/{doc}/restore/")
    assert res.status_code == 429 and res.json_body["error"]["details"]["kind"] == "documents"
    assert Document.objects.get(pk=doc).deleted_at is not None


def test_a_document_still_waiting_for_its_upload_cannot_be_trashed(api, fake_storage):
    doc = reserve(api).json_body["document"]["id"]
    res = api.delete(f"/notes/documents/{doc}/")
    assert res.status_code == 409 and res.json_body["error"]["code"] == "not_trashable"


def test_permanent_delete_frees_the_quota_at_once_and_the_object_within_the_worker_run(api, fake_storage):
    doc = uploaded(api, fake_storage)
    document = Document.objects.get(pk=doc)
    attachment_id, path = document.attachment_id, document.attachment.path
    mark = make_annotation(document)
    res = api.delete(f"/notes/documents/{doc}/?permanent=1")
    assert res.status_code == 200 and res.json_body == {"id": doc, "purged": True}
    assert usage() == (0, 0)  # free at once
    assert not Document.objects.exists() and not Annotation.objects.filter(pk=mark.pk).exists()
    assert (
        Attachment.objects.get(pk=attachment_id).status == "deleting"
        and ("notes-private", path) in fake_storage.objects
    )
    jobs.run_pending(types=["media.delete"])
    assert not Attachment.objects.exists() and not fake_storage.objects
    assert usage() == (0, 0)  # the delete job did not release a second time


def test_a_second_students_quota_is_untouched_by_the_purge_of_a_neighbour(api, other_api, fake_storage):
    mine = uploaded(api, fake_storage)
    theirs = other_api.post(
        "/notes/documents/",
        {
            "client_id": "5a3f0c1e-1111-4222-8333-444455556666",
            "filename": "x.pdf",
            "bytes": MB,
            "mime": "application/pdf",
        },
    )
    assert theirs.status_code == 201
    api.delete(f"/notes/documents/{mine}/?permanent=1")
    jobs.run_pending(types=["media.delete"])
    assert usage() == (0, 0) and QuotaUsage.objects.exclude(pk=ALICE).get().docs_active == 1


def test_purging_removes_the_cover_and_export_files_and_orphans_unshared_content(api, fake_storage):
    content = make_content()
    cover = make_attachment(ALICE, kind="note_image", mime="image/webp", ext="webp", bytes=2000)
    document = make_document(ALICE, content=content, cover_attachment=cover)
    export_file = make_attachment(ALICE, kind="note_export", bytes=0)
    make_export(document, attachment=export_file, status="done")
    QuotaUsage.objects.create(user_id=ALICE, bytes_used=document.bytes + 2000, docs_active=1)
    api.delete(f"/notes/documents/{document.id}/?permanent=1")
    assert {a.status for a in Attachment.objects.all()} == {"deleting"} and Attachment.objects.count() == 3
    assert not ExportJob.objects.exists()
    assert FileContent.objects.get(pk=content.pk).orphaned_at is not None
    jobs.run_pending(types=["media.delete"])
    assert not Attachment.objects.exists()
    assert usage() == (0, 0)  # the cover's bytes were released by the media job, once


def test_content_shared_with_another_document_is_not_orphaned(api, fake_storage):
    content = make_content()
    keep = make_document(ALICE, content=content)
    gone = make_document(ALICE, content=content)
    QuotaUsage.objects.create(user_id=ALICE, bytes_used=2000, docs_active=2)
    api.delete(f"/notes/documents/{gone.id}/?permanent=1")
    assert FileContent.objects.get(pk=content.pk).orphaned_at is None and Document.objects.filter(pk=keep.pk).exists()


def test_rejected_and_expired_documents_hold_no_quota_so_deleting_them_releases_nothing(api, fake_storage):
    QuotaUsage.objects.create(user_id=ALICE, bytes_used=10 * MB, docs_active=3)
    for status in ("rejected", "expired"):
        doc = make_document(ALICE, status=status, attachment=make_attachment(ALICE, bytes=0, status="rejected"))
        assert api.delete(f"/notes/documents/{doc.id}/?permanent=1").status_code == 200
    assert usage() == (10 * MB, 3)


def test_the_thirty_day_purge_removes_old_trash_and_releases_quota(api, fake_storage):
    doc = uploaded(api, fake_storage)
    api.delete(f"/notes/documents/{doc}/")
    assert document_trash.purge_expired() == 0
    Document.objects.filter(pk=doc).update(purge_after=timezone.now() - timedelta(minutes=1))
    assert document_trash.purge_expired() == 1 and not Document.objects.exists() and usage() == (0, 0)


def test_no_service_ever_rewrites_the_original_object(api, fake_storage):
    doc = uploaded(api, fake_storage)
    document = Document.objects.get(pk=doc)
    key = (document.attachment.bucket, document.attachment.path)
    before = fake_storage.objects[key]
    api.patch(f"/notes/documents/{doc}/", {"title": "Renamed"})
    api.put(f"/notes/documents/{doc}/progress/", {"last_page": 1, "last_zoom": "fit"})
    api.delete(f"/notes/documents/{doc}/")
    api.post(f"/notes/documents/{doc}/restore/")
    assert fake_storage.objects[key] is before


def test_the_service_refuses_a_restore_over_the_limit_directly():
    QuotaUsage.objects.create(user_id=ALICE, bytes_used=600 * MB, docs_active=1)
    doc = make_document(ALICE, deleted_at=timezone.now(), purge_after=timezone.now() + timedelta(days=1))
    with pytest.raises(QuotaExceeded):
        document_trash.restore_document(ALICE, doc.id)
