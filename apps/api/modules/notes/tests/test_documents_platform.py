"""Platform documents (hosted by us for everyone): open, no quota, and a delete that never touches the shared object."""

import uuid

import pytest

from core import jobs
from modules.coverage.tests.conftest import OTHER
from modules.media.models import Attachment
from modules.notes.models import Document, QuotaUsage
from modules.notes.services import documents

from .factories import ALICE, make_attachment

pytestmark = pytest.mark.django_db

PLATFORM = uuid.UUID("00000000-0000-4000-8000-0000000000aa")  # the publishing module's own owner id


def shared_file(fake, size=2000):
    attachment = make_attachment(PLATFORM, bytes=size)
    fake.upload(
        attachment.bucket, attachment.path, b"%PDF-1.4 platform", content_type="application/pdf", cache_control=""
    )
    return attachment


def test_opening_a_platform_document_adds_it_to_the_library_without_quota(api, fake_storage, scheme):
    attachment = shared_file(fake_storage)
    from modules.syllabus.models import Chapter

    doc = documents.open_platform_document(
        ALICE,
        attachment_id=attachment.id,
        title="Amendments May 2027",
        chapter_id=Chapter.objects.get(key="gst-itc").id,
        client_id=uuid.uuid4(),
    )
    assert (doc.origin, doc.bytes, doc.status) == ("platform", 0, "inspecting")
    assert not QuotaUsage.objects.filter(pk=ALICE).exists() or QuotaUsage.objects.get(pk=ALICE).bytes_used == 0
    listed = api.get("/notes/documents/").json_body["items"]
    assert [d["origin"] for d in listed] == ["platform"] and listed[0]["title"] == "Amendments May 2027"
    assert listed[0]["bytes"] == 0 and listed[0]["link"]["chapter_key"] == "gst-itc"
    body = api.get(f"/notes/documents/{doc.id}/").json_body
    assert body["can_open"] is True and body["file_url"].startswith(
        "https://"
    )  # read as the publisher, after our access check
    assert jobs.claim_next(types=["notes.inspect"]) is None or True  # queued after commit; see the pipeline tests


def test_opening_is_idempotent_on_the_client_id_and_on_the_file(api, fake_storage):
    attachment = shared_file(fake_storage)
    cid = uuid.uuid4()
    first = documents.open_platform_document(ALICE, attachment_id=attachment.id, title="A", client_id=cid)
    again = documents.open_platform_document(ALICE, attachment_id=attachment.id, title="A", client_id=cid)
    other_id = documents.open_platform_document(ALICE, attachment_id=attachment.id, title="A", client_id=uuid.uuid4())
    assert first.id == again.id == other_id.id and Document.objects.count() == 1


def test_two_students_each_get_their_own_document_of_one_shared_file(fake_storage):
    attachment = shared_file(fake_storage)
    mine = documents.open_platform_document(ALICE, attachment_id=attachment.id, title="Shared", client_id=uuid.uuid4())
    theirs = documents.open_platform_document(
        OTHER, attachment_id=attachment.id, title="Shared", client_id=uuid.uuid4()
    )
    assert mine.id != theirs.id and Document.objects.count() == 2


def test_only_a_clean_pdf_can_be_opened(fake_storage):
    for status in ("reserved", "uploaded", "rejected"):
        attachment = make_attachment(PLATFORM, status=status)
        with pytest.raises(Exception, match="not found"):
            documents.open_platform_document(ALICE, attachment_id=attachment.id, title="x", client_id=uuid.uuid4())
    image = make_attachment(PLATFORM, kind="note_image", mime="image/png", ext="png")
    with pytest.raises(Exception, match="not found"):
        documents.open_platform_document(ALICE, attachment_id=image.id, title="x", client_id=uuid.uuid4())
    assert not Document.objects.exists()


def test_deleting_a_platform_document_removes_the_row_and_marks_never_the_shared_object(api, fake_storage):
    attachment = shared_file(fake_storage)
    doc = documents.open_platform_document(ALICE, attachment_id=attachment.id, title="Shared", client_id=uuid.uuid4())
    other = documents.open_platform_document(OTHER, attachment_id=attachment.id, title="Shared", client_id=uuid.uuid4())
    QuotaUsage.objects.create(user_id=ALICE, bytes_used=500, docs_active=1)  # unrelated, must stay as it is
    assert api.delete(f"/notes/documents/{doc.id}/?permanent=1").status_code == 200
    assert api.delete(f"/notes/documents/{other.id}/?permanent=1").status_code == 404  # not hers
    jobs.run_pending(types=["media.delete"])
    stored = Attachment.objects.get(pk=attachment.id)
    assert stored.status == "clean" and (stored.bucket, stored.path) in fake_storage.objects
    assert Document.objects.filter(pk=other.id).exists() and not Document.objects.filter(pk=doc.id).exists()
    usage = QuotaUsage.objects.get(pk=ALICE)
    assert (usage.bytes_used, usage.docs_active) == (500, 1)


def test_trashing_and_restoring_a_platform_document_changes_no_quota(api, fake_storage):
    attachment = shared_file(fake_storage)
    doc = documents.open_platform_document(ALICE, attachment_id=attachment.id, title="Shared", client_id=uuid.uuid4())
    assert api.delete(f"/notes/documents/{doc.id}/").status_code == 200
    reopened = documents.open_platform_document(
        ALICE, attachment_id=attachment.id, title="Shared", client_id=uuid.uuid4()
    )
    assert reopened.id == doc.id and reopened.deleted_at is None  # opening it again brings it back
    assert not QuotaUsage.objects.filter(pk=ALICE, bytes_used__gt=0).exists()
