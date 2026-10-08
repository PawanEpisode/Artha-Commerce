"""
Document writes (ERD 1.2, 3.2, 6.4): reserve, complete, abort, edit, progress, platform documents. The bytes never pass through
the API; `media` owns the attachment, the signed upload and the scan, and this module owns the document row around it.

Rules worth knowing before reading the code:
- Limits are checked before any quota moves, in the order the student can fix them: type, size, pages, then quota.
- `reserve_document` is idempotent on `client_id`: a replay returns the stored row (and a fresh upload URL while the file is
  still expected), takes no quota and charges nothing.
- Quota is taken by `media.create_upload('note_pdf')` through the kind's `reserve` hook (one conditional UPDATE for bytes and
  the slot together) and returned by the hooks and jobs in this module exactly once: whoever flips the document to a
  released state (`rejected`, `expired`, purged) also zeroes the attachment's bytes, so the media delete job never releases twice.
- The student's original object is never rewritten by any service here.
"""

from __future__ import annotations

import os
import re
import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework.exceptions import NotFound, ValidationError

from core.storage import StorageError
from modules.media import services as media
from modules.media.errors import FileTooLarge, StorageUnavailable, UnsupportedType, UploadMissing
from modules.media.models import Attachment

from .. import events
from ..errors import DocumentConflict, NotAbortable, NotUploaded, QuotaExceeded, TooManyPages
from ..models import Document, ItemTag
from . import document_ranges, links, quota, tags

PDF_KIND = "note_pdf"
PDF_MIME = "application/pdf"  # `media_kinds.PDF_MIME`; not imported, that module imports the services
RESERVATION_SLACK = timedelta(seconds=60)  # the document expires a minute before the media sweep would delete its file
ZOOM = re.compile(r"^(fit|[1-9][0-9]{1,3})$")
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")
EDITABLE = ("title", "source_kind", "edition_label", "chapter_id", "topic_id", "tag_ids")
REJECT_REASONS = frozenset(
    {"type_mismatch", "malware", "pdf_corrupt", "too_many_pages", "too_large", "decode_failed", "policy"}
)


@dataclass(frozen=True)
class Reservation:
    document: Document
    upload: media.Upload | None  # None once the file has been confirmed
    created: bool


def _now() -> datetime:
    return timezone.now()


# --- Lookups ------------------------------------------------------------------------------------------------------------
def get_owned(user_id, document_id) -> Document:
    document = Document.objects.filter(pk=document_id, user_id=user_id).first()
    if document is None:
        raise NotFound("Document not found.")
    return document


def get_locked(user_id, document_id) -> Document:
    """The student's document with its row locked; the same 404 for a missing one and for someone else's."""
    document = Document.objects.select_for_update().filter(pk=document_id, user_id=user_id).first()
    if document is None:
        raise NotFound("Document not found.")
    return document


# --- Names --------------------------------------------------------------------------------------------------------------
def clean_filename(filename: str) -> str:
    """Display copy of the file name: no directories, no control characters, at most 255 characters."""
    base = os.path.basename(_CONTROL.sub("", filename).replace("\\", "/")).strip()
    return base[:255]


def title_from_filename(filename: str) -> str:
    stem = os.path.splitext(clean_filename(filename))[0]
    return " ".join(stem.replace("_", " ").split())[:200] or "Untitled PDF"


def clean_title(title: str) -> str:
    cleaned = " ".join(_CONTROL.sub(" ", title).split())[:200]
    if not cleaned:
        raise ValidationError({"title": "A title cannot be empty."})
    return cleaned


# --- Reserve ------------------------------------------------------------------------------------------------------------
def _resume_upload(document: Document) -> media.Upload | None:
    """A fresh signed upload for a replayed reservation, while the file is still expected."""
    attachment = document.attachment
    if document.status != Document.Status.RESERVED or attachment.status != Attachment.Status.RESERVED:
        return None
    if attachment.expires_at is None or attachment.expires_at < _now():
        return None
    try:
        signed = media.get_storage().create_signed_upload(attachment.bucket, attachment.path)
    except StorageError as exc:
        raise StorageUnavailable from exc
    headers = {"content-type": attachment.mime, "x-upsert": "false"}
    return media.Upload(attachment, signed.url, headers, attachment.expires_at)


def reserve_document(
    user_id,
    *,
    client_id: uuid.UUID,
    filename: str,
    bytes: int,  # noqa: A002 - the API's own field name
    mime: str,
    page_count_hint: int | None = None,
    source_kind: str = Document.SourceKind.OTHER,
    chapter_id: uuid.UUID | None = None,
    topic_id: uuid.UUID | None = None,
) -> Reservation:
    existing = Document.objects.select_related("attachment").filter(user_id=user_id, client_id=client_id).first()
    if existing is not None:
        return Reservation(existing, _resume_upload(existing), False)
    limits = quota.limits_for(user_id)
    if mime != PDF_MIME:
        raise UnsupportedType(extra={"allowed": [PDF_MIME]})
    if bytes > limits.file_bytes:
        raise FileTooLarge(extra={"limit_mb": limits.max_file_mb})
    if page_count_hint is not None and page_count_hint > limits.max_pages:
        raise TooManyPages(extra={"limit": limits.max_pages})
    link = links.link_columns(chapter_id, topic_id)
    try:
        with transaction.atomic():
            upload = media.create_upload(user_id, PDF_KIND, mime=mime, bytes=bytes)
            document = Document.objects.create(
                user_id=user_id,
                client_id=client_id,
                title=title_from_filename(filename),
                original_filename=clean_filename(filename),
                attachment=upload.attachment,
                bytes=bytes,
                page_count=page_count_hint,
                source_kind=source_kind,
                reservation_expires_at=upload.expires_at - RESERVATION_SLACK,
                **link,
            )
            quota.charge_monthly(user_id, "uploads")
            events.announce_counts(user_id, [links.link_key(document)], "created")
    except QuotaExceeded as exc:
        from .. import selectors  # local: selectors import the services' quota helpers

        exc.extra = {**(exc.extra or {}), "largest_documents": selectors.largest_documents(user_id)}
        raise
    except IntegrityError:  # two requests with one client_id raced: the loser returns the winner's row
        winner = Document.objects.select_related("attachment").filter(user_id=user_id, client_id=client_id).first()
        if winner is None:
            raise
        return Reservation(winner, _resume_upload(winner), False)
    return Reservation(document, upload, True)


# --- Complete and abort --------------------------------------------------------------------------------------------------
def _reason_of(attachment: Attachment) -> str:
    return attachment.status_reason if attachment.status_reason in REJECT_REASONS else "policy"


@transaction.atomic
def complete_document(user_id, document_id) -> Document:
    """
    Confirms the upload. Idempotent: anything past `reserved` is returned as it is. The document's status follows the
    attachment `media.complete_upload` returns: `uploaded` (waiting for the scanner) is `scanning`, `clean` is `inspecting`
    (the `on_clean` hook queues the inspection after commit) and `rejected` is `rejected` with the reason. 409
    `not_uploaded` until the object is in storage, and for a reservation that lapsed.
    """
    document = get_locked(user_id, document_id)
    if document.status == Document.Status.EXPIRED:
        raise NotUploaded("This upload expired. Start it again.")
    if document.status != Document.Status.RESERVED:
        return document
    try:
        attachment = media.complete_upload(user_id, document.attachment_id)
    except UploadMissing as exc:
        raise NotUploaded(str(exc.detail)) from exc
    now = _now()
    document.reservation_expires_at = None
    if attachment.status == Attachment.Status.REJECTED:
        document.status, document.status_reason = Document.Status.REJECTED, _reason_of(attachment)
    elif attachment.status == Attachment.Status.CLEAN:
        document.status = Document.Status.INSPECTING
    else:
        document.status = Document.Status.SCANNING
    document.updated_at = now
    document.save(update_fields=["status", "status_reason", "reservation_expires_at", "updated_at"])
    return document


def release_reserved(document: Document, attachment: Attachment, *, new_status: str) -> bool:
    """
    The one way a reserved, never-confirmed upload gives its quota back (abort and expiry). Caller holds the document lock.
    False (and nothing changed) when `media` already took the attachment over (its sweep marked it `deleting`): the media
    delete job releases the quota then, so releasing here too would count it twice.
    """
    if attachment.status != Attachment.Status.RESERVED:
        return False
    quota.release_document(str(document.user_id), attachment.bytes)
    Attachment.objects.filter(pk=attachment.pk).update(bytes=0, expires_at=None, updated_at=_now())
    document.status, document.status_reason, document.reservation_expires_at = new_status, None, None
    document.save(update_fields=["status", "status_reason", "reservation_expires_at", "updated_at"])
    events.announce_counts(document.user_id, [links.link_key(document)], "trashed")
    return True


def _abort_parts_after_commit(document: Document) -> None:
    """A cancelled or lapsed upload sent in parts leaves no half-file in the bucket (best effort, after the commit)."""
    if document.resumable_upload_id:
        from . import resumable  # local: it imports this module

        transaction.on_commit(lambda: resumable.abort_quietly(document))


@transaction.atomic
def abort_document(user_id, document_id) -> Document:
    """The student cancelled before the upload finished. Idempotent. 409 `not_abortable` once the file was confirmed."""
    document = get_locked(user_id, document_id)
    if document.status == Document.Status.EXPIRED:
        return document
    if document.status != Document.Status.RESERVED:
        raise NotAbortable
    attachment = Attachment.objects.select_for_update().get(pk=document.attachment_id)
    _abort_parts_after_commit(document)
    if not release_reserved(document, attachment, new_status=Document.Status.EXPIRED):
        document.status = Document.Status.EXPIRED  # the media sweep got there first; the row goes with the attachment
    return document


# --- Rejection by the worker ----------------------------------------------------------------------------------------------
def reject_stored(document: Document, reason: str) -> None:
    """
    The inspection found a file the product will not keep. Removes the object, gives the quota back once and keeps the row
    as `rejected` with the reason, like `media` does for a scan verdict (the attachment becomes `rejected`, `bytes` 0).
    Caller holds the document lock. A platform document only changes status: the shared object and its quota are not ours.
    """
    reason = reason if reason in REJECT_REASONS else "policy"
    if document.origin == Document.Origin.UPLOAD:
        attachment = Attachment.objects.select_for_update().get(pk=document.attachment_id)
        try:
            media.get_storage().delete(attachment.bucket, [attachment.path])
        except StorageError as exc:
            raise RuntimeError("Storage refused the delete.") from exc  # the job retries with backoff
        if attachment.bytes:
            quota.release_document(str(document.user_id), attachment.bytes)
        Attachment.objects.filter(pk=attachment.pk).update(
            status=Attachment.Status.REJECTED, status_reason=reason, bytes=0, updated_at=_now()
        )
    document.status, document.status_reason, document.updated_at = Document.Status.REJECTED, reason, _now()
    document.save(update_fields=["status", "status_reason", "updated_at"])
    events.announce_counts(document.user_id, [links.link_key(document)], "trashed")


# --- Edit -----------------------------------------------------------------------------------------------------------------
def _set_tags(user_id, document: Document, tag_ids: Iterable[uuid.UUID]) -> None:
    chosen = tags.owned_tags(user_id, tag_ids)
    keep = {t.id for t in chosen}
    ItemTag.objects.filter(document=document).exclude(tag_id__in=keep).delete()
    have = set(ItemTag.objects.filter(document=document).values_list("tag_id", flat=True))
    ItemTag.objects.bulk_create(
        [ItemTag(user_id=user_id, tag=t, document=document) for t in chosen if t.id not in have], ignore_conflicts=True
    )


@transaction.atomic
def update_document(user_id, document_id, *, base_rev: int | None, changes: dict[str, Any]) -> Document:
    """
    Metadata edit. A stale `base_rev` is `DocumentConflict` and writes nothing; without one the write wins. Changing the
    default chapter re-links the marks that inherit it (`document_ranges.relink_marks`) and announces both chapters' counts.
    """
    document = get_locked(user_id, document_id)
    if base_rev is not None and base_rev != document.rev:
        raise DocumentConflict
    old_key = links.link_key(document)
    changed = False
    if "title" in changes and changes["title"] != document.title:
        document.title, changed = clean_title(changes["title"]), True
    if "source_kind" in changes and changes["source_kind"] != document.source_kind:
        document.source_kind, changed = changes["source_kind"], True
    if "edition_label" in changes and (changes["edition_label"] or None) != document.edition_label:
        document.edition_label, changed = changes["edition_label"] or None, True
    relinked_keys: list = []
    if "chapter_id" in changes or "topic_id" in changes:
        chapter_id = changes.get("chapter_id", document.chapter_id)
        topic_id = changes.get("topic_id", document.topic_id if "chapter_id" not in changes else None)
        if (chapter_id, topic_id) != (document.chapter_id, document.topic_id):
            for column, value in links.link_columns(chapter_id, topic_id).items():
                setattr(document, column, value)
            changed = True
            relinked_keys = document_ranges.relink_marks(document).keys
    if "tag_ids" in changes:
        _set_tags(user_id, document, changes["tag_ids"])
        changed = True
    if changed:
        document.rev += 1
        document.save()
        new_key = links.link_key(document)
        if new_key != old_key or relinked_keys:
            events.announce_counts(user_id, [old_key, new_key, *relinked_keys], "relinked")
    return document


def update_progress(
    user_id, document_id, *, last_page: int, last_zoom: str, page_tone: str | None, set_tone: bool
) -> Document:
    """Last write wins and is idempotent: no `rev`, no conflict. A page past the end is clamped when the count is known."""
    document = get_owned(user_id, document_id)
    if document.page_count:
        last_page = min(last_page, document.page_count)
    fields = {"last_page": last_page, "last_zoom": last_zoom, "last_opened_at": _now()}
    if set_tone:
        fields["page_tone"] = page_tone
    Document.objects.filter(pk=document.pk, user_id=user_id).update(**fields)
    document.refresh_from_db()
    return document


# --- Platform documents -----------------------------------------------------------------------------------------------------
@transaction.atomic
def open_platform_document(
    user_id,
    *,
    attachment_id: uuid.UUID,
    title: str,
    chapter_id: uuid.UUID | None = None,
    client_id: uuid.UUID,
) -> Document:
    """
    Adds a document hosted by us for every student (study material, amendments, X-04) to the student's library so it opens in
    the reader and takes marks like any PDF. Origin `platform`, 0 bytes, no quota. The attachment belongs to the publishing
    module and is only ever READ here (`media.signed_url` as its owner); deleting the document never removes the shared
    object. Idempotent on `client_id` and on the attachment: opening the same file again returns (and un-trashes) the row.
    """
    attachment = Attachment.objects.filter(pk=attachment_id).exclude(status=Attachment.Status.DELETING).first()
    if attachment is None or attachment.status != Attachment.Status.CLEAN or attachment.mime != PDF_MIME:
        raise NotFound("Document not found.")
    existing = (
        Document.objects.select_for_update()
        .filter(user_id=user_id, origin=Document.Origin.PLATFORM)
        .filter(Q(client_id=client_id) | Q(attachment_id=attachment_id))
        .first()
    )
    if existing is not None:
        if existing.deleted_at is not None:
            existing.deleted_at = existing.purge_after = None
            existing.rev += 1
            existing.save()
            events.announce_counts(user_id, [links.link_key(existing)], "restored")
        return existing
    document = Document.objects.create(
        user_id=user_id,
        client_id=client_id,
        origin=Document.Origin.PLATFORM,
        title=clean_title(title),
        original_filename="",
        attachment=attachment,
        bytes=0,
        status=Document.Status.INSPECTING,
        **links.link_columns(chapter_id, None),
    )
    transaction.on_commit(lambda: _queue_inspect(document.id))
    events.announce_counts(user_id, [links.link_key(document)], "created")
    return document


def _queue_inspect(document_id) -> None:
    from core import jobs

    from ..jobs import JOB_INSPECT

    jobs.enqueue(JOB_INSPECT, {"document_id": str(document_id)}, dedupe_key=f"{JOB_INSPECT}:{document_id}")
