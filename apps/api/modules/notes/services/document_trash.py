"""
Trash, restore, permanent delete and the sweeps of documents (ERD 6.4, 1.2).

Quota: a trashed document still holds its bytes and its slot (the file is kept 30 days), so trashing changes no counter and
restoring only checks the student is not over a limit that shrank meanwhile. A permanent delete (the student's, or the 30-day
purge) gives the quota back AT ONCE and queues the object removal through `media`:

  1. release the quota and zero the attachment's bytes (so the media delete job cannot release it a second time),
  2. delete the document row (marks, ranges, tag links and export jobs cascade),
  3. only then queue the attachment deletes: deleting an attachment cascades to the document row that points at it.

A platform document never removes the shared object: only the student's row, marks and tags go.
"""

from __future__ import annotations

from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from modules.media import services as media
from modules.media.models import Attachment

from .. import events
from ..errors import NotTrashable
from ..models import Document, ExportJob, QuotaUsage
from . import content, documents, links, quota
from .quota import _exceeded

TRASH_DAYS = 30
EXPIRED_KEEP = timedelta(days=1)  # an expired reservation stays visible this long, then the row and its object go
RELEASED = (Document.Status.REJECTED, Document.Status.EXPIRED)


@transaction.atomic
def trash_document(user_id, document_id) -> Document:
    """Idempotent. A document still waiting for its upload cannot be trashed (cancel it instead): 409 `not_trashable`."""
    document = documents.get_locked(user_id, document_id)
    if document.deleted_at is not None:
        return document
    if document.status == Document.Status.RESERVED:
        raise NotTrashable
    now = timezone.now()
    document.deleted_at, document.purge_after = now, now + timedelta(days=TRASH_DAYS)
    document.rev += 1
    document.save()
    events.announce_counts(user_id, [links.link_key(document)], "trashed")
    return document


def _check_within_limits(user_id) -> None:
    """Restoring adds nothing to the counters; it only refuses a student who is over a limit that shrank after the trash."""
    limits = quota.limits_for(user_id)
    usage = QuotaUsage.objects.filter(pk=user_id).first()
    if usage is None:
        return
    if usage.docs_active > limits.max_documents:
        raise _exceeded(user_id, "documents", usage.docs_active, limits.max_documents)
    if usage.bytes_used > limits.storage_bytes:
        raise _exceeded(user_id, "storage", usage.bytes_used, limits.storage_bytes)


@transaction.atomic
def restore_document(user_id, document_id) -> Document:
    document = documents.get_locked(user_id, document_id)
    if document.deleted_at is None:
        return document
    _check_within_limits(user_id)
    document.deleted_at = document.purge_after = None
    document.rev += 1
    document.save()
    events.announce_counts(user_id, [links.link_key(document)], "restored")
    return document


def _purge_locked(document: Document) -> None:
    """Removes one document for good. The caller holds its row lock inside a transaction."""
    user_id = document.user_id
    shared_object = document.origin == Document.Origin.PLATFORM
    doomed: set = set()
    if not shared_object:
        attachment = Attachment.objects.select_for_update().filter(pk=document.attachment_id).first()
        if attachment is not None:
            if document.status not in RELEASED:
                quota.release_document(str(user_id), attachment.bytes)
            Attachment.objects.filter(pk=attachment.pk).update(bytes=0)
            doomed.add(attachment.pk)
    if document.cover_attachment_id:
        doomed.add(document.cover_attachment_id)
    doomed |= set(
        ExportJob.objects.filter(document=document, attachment__isnull=False).values_list("attachment_id", flat=True)
    )
    live, key, content_id = document.deleted_at is None, links.link_key(document), document.content_id
    document.delete()  # cascades marks, ranges, tag links and export jobs
    content.mark_orphaned([content_id])
    media.queue_delete(doomed)  # inside the transaction: a rollback queues nothing, and the row is already gone
    if live:
        events.announce_counts(user_id, [key], "trashed")


@transaction.atomic
def purge_document(user_id, document_id) -> None:
    """The student's permanent delete (`DELETE documents/{id}/?permanent=1`), from any state. Quota is free at once."""
    _purge_locked(documents.get_locked(user_id, document_id))


def purge_expired(*, now=None, limit: int = 100) -> int:
    """Permanently deletes documents whose 30 trash days are over, and expired reservations kept long enough. Returns the count."""
    now = now or timezone.now()
    ids = list(
        Document.objects.filter(deleted_at__isnull=False, purge_after__lte=now).values_list("id", flat=True)[:limit]
    )
    ids += list(
        Document.objects.filter(status=Document.Status.EXPIRED, updated_at__lt=now - EXPIRED_KEEP).values_list(
            "id", flat=True
        )[: max(limit - len(ids), 0)]
    )
    purged = 0
    for document_id in ids:
        with transaction.atomic():
            document = Document.objects.select_for_update().filter(pk=document_id).first()
            if document is not None:
                _purge_locked(document)
                purged += 1
    return purged


def expire_reservations(*, now=None, limit: int = 200) -> int:
    """Reserved documents past their `reservation_expires_at` become `expired` and give their quota back. Returns the count."""
    now = now or timezone.now()
    ids = list(
        Document.objects.filter(status=Document.Status.RESERVED, reservation_expires_at__lt=now).values_list(
            "id", flat=True
        )[:limit]
    )
    expired = 0
    for document_id in ids:
        with transaction.atomic():
            document = Document.objects.select_for_update().filter(pk=document_id, status="reserved").first()
            if document is None:
                continue
            attachment = Attachment.objects.select_for_update().filter(pk=document.attachment_id).first()
            documents._abort_parts_after_commit(document)
            if attachment is not None and documents.release_reserved(
                document, attachment, new_status=Document.Status.EXPIRED
            ):
                expired += 1
    return expired
