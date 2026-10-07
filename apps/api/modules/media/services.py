"""
Attachment writes: reserve quota and a signed upload URL, confirm the upload, serve signed read URLs, delete objects.

Flow (the bytes never pass through our servers):
  1. `create_upload`   validate type and size, take quota atomically through the kind's hook, write the row `reserved`,
                       return a one-object signed upload URL.
  2. the browser PUTs the file to storage.
  3. `complete_upload` checks the object exists; kinds with `scan="none"` become `clean` at once, others wait for the scanner.
  4. other modules reference only `clean` attachments (`require_clean`) and serve them with `signed_url`.
Deleting is a queued job (`media.delete`): the object goes first (idempotent), then quota is released and the row removed
in one transaction, so a retry can never release twice.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import NotFound

from core import jobs
from core.errors import FeatureDisabled
from core.feature_flags import flag_enabled
from core.storage import StorageError, get_storage

from . import registry
from .errors import FileTooLarge, NotReady, StorageUnavailable, UnsupportedType, UploadMissing
from .models import Attachment

logger = logging.getLogger(__name__)

JOB_DELETE = "media.delete"
JOB_EXPIRE = "media.expire_reservations"


@dataclass(frozen=True)
class Upload:
    attachment: Attachment
    url: str
    headers: dict[str, str]
    expires_at: datetime


@dataclass(frozen=True)
class SignedRead:
    url: str
    expires_at: datetime


def _now() -> datetime:
    return timezone.now()


def get_owned(user_id, attachment_id, kind: str | None = None) -> Attachment:
    """The student's own attachment (404 for anyone else's or one being deleted)."""
    qs = Attachment.objects.filter(pk=attachment_id, user_id=user_id).exclude(status=Attachment.Status.DELETING)
    if kind:
        qs = qs.filter(kind=kind)
    attachment = qs.first()
    if attachment is None:
        raise NotFound("Attachment not found.")
    return attachment


def require_clean(user_id, attachment_id, kind: str | None = None) -> Attachment:
    """For modules that reference an attachment: it must be the student's, of this kind, and safe to use."""
    attachment = get_owned(user_id, attachment_id, kind)
    if attachment.status != Attachment.Status.CLEAN:
        raise NotReady
    return attachment


def clean_attachment_ids(user_id, attachment_ids, kind: str) -> set[uuid.UUID]:
    """Which of these ids are the student's own, `clean` attachments of `kind`: one query, for validating a body's images."""
    return set(
        Attachment.objects.filter(
            pk__in=list(attachment_ids), user_id=user_id, kind=kind, status=Attachment.Status.CLEAN
        ).values_list("id", flat=True)
    )


def create_upload(user_id, kind: str, *, mime: str, bytes: int) -> Upload:  # noqa: A002 - the API's own field name
    spec = registry.get_kind(kind)
    if spec.flag and not flag_enabled(spec.flag, user_id):
        raise FeatureDisabled
    if mime not in spec.mimes:
        raise UnsupportedType(extra={"allowed": sorted(spec.mimes)})
    limit = spec.max_bytes(str(user_id))
    if bytes < 1 or bytes > limit:
        raise FileTooLarge(extra={"max_bytes": limit})
    attachment_id = uuid.uuid4()
    expires_at = _now() + timedelta(minutes=spec.reservation_minutes)
    try:
        with transaction.atomic():  # a failed signing call gives the reserved quota back with the rollback
            spec.reserve(str(user_id), bytes)
            attachment = Attachment.objects.create(
                id=attachment_id,
                user_id=user_id,
                kind=kind,
                bucket=spec.bucket,
                path=spec.path_for(str(user_id), attachment_id, mime),
                bytes=bytes,
                mime=mime,
                expires_at=expires_at,
            )
            signed = get_storage().create_signed_upload(attachment.bucket, attachment.path)
    except StorageError as exc:
        logger.warning("Signed upload failed: %s", exc)
        raise StorageUnavailable from exc
    headers = {"content-type": mime, "x-upsert": "false"}
    return Upload(attachment, signed.url, headers, expires_at)


@transaction.atomic
def complete_upload(user_id, attachment_id) -> Attachment:
    """Idempotent. 409 `upload_missing` until the object is really in storage; a reservation that lapsed is refused."""
    attachment = Attachment.objects.select_for_update().filter(pk=attachment_id, user_id=user_id).first()
    if attachment is None or attachment.status == Attachment.Status.DELETING:
        raise NotFound("Attachment not found.")
    if attachment.status != Attachment.Status.RESERVED:
        return attachment
    if attachment.is_expired_reservation:
        raise UploadMissing("This upload expired. Start it again.")
    try:
        present = get_storage().exists(attachment.bucket, attachment.path)
    except StorageError as exc:
        raise StorageUnavailable from exc
    if not present:
        raise UploadMissing
    spec = registry.get_kind(attachment.kind)
    attachment.status = Attachment.Status.UPLOADED
    attachment.expires_at = None
    if spec.scan == "none":
        attachment.status = Attachment.Status.CLEAN
    attachment.save(update_fields=["status", "expires_at", "updated_at"])
    if attachment.status == Attachment.Status.CLEAN and spec.on_clean:
        transaction.on_commit(lambda: spec.on_clean(attachment.id))
    return attachment


def signed_url(user_id, attachment_id) -> SignedRead:
    """A short-lived read URL for the owner's clean attachment. The URL is a capability: never log or store it."""
    attachment = require_clean(user_id, attachment_id)
    spec = registry.get_kind(attachment.kind)
    try:
        url = get_storage().create_signed_url(attachment.bucket, attachment.path, spec.read_url_seconds)
    except StorageError as exc:
        raise StorageUnavailable from exc
    return SignedRead(url, _now() + timedelta(seconds=spec.read_url_seconds))


# --- Deleting -----------------------------------------------------------------------------------------------------------
def queue_delete(attachment_ids) -> int:
    """Marks the attachments `deleting` (they stop being served at once) and queues the object removal. Returns the count."""
    ids = list(attachment_ids)
    if not ids:
        return 0
    count = Attachment.objects.filter(pk__in=ids).update(status=Attachment.Status.DELETING, updated_at=_now())
    for attachment_id in ids:
        jobs.enqueue(JOB_DELETE, {"attachment_id": str(attachment_id)}, dedupe_key=f"{JOB_DELETE}:{attachment_id}")
    return count


def run_delete_job(payload: dict) -> dict:
    """Removes the object, then releases quota and the row together. A missing row means a previous run finished."""
    attachment = Attachment.objects.filter(pk=payload["attachment_id"]).first()
    if attachment is None:
        return {"deleted": False}
    try:
        get_storage().delete(attachment.bucket, [attachment.path])
    except StorageError as exc:
        raise RuntimeError(f"Storage refused the delete: {exc}") from exc  # the job retries with backoff
    with transaction.atomic():
        locked = Attachment.objects.select_for_update().filter(pk=attachment.pk).first()
        if locked is not None:
            registry.get_kind(locked.kind).release(str(locked.user_id), locked.bytes)
            locked.delete()
    return {"deleted": True}


def expire_reservations(*, limit: int = 200) -> int:
    """Releases uploads that were started and never completed (their quota is held until then). Returns how many."""
    ids = list(
        Attachment.objects.filter(status=Attachment.Status.RESERVED, expires_at__lt=_now()).values_list(
            "id", flat=True
        )[:limit]
    )
    return queue_delete(ids)


def run_expire_job(payload: dict) -> dict:
    return {"released": expire_reservations()}


def delete_all_for_user(user_id) -> dict:
    """Account erasure: every object the student owns is queued for removal (the files go within the next worker runs)."""
    ids = list(Attachment.objects.filter(user_id=user_id).values_list("id", flat=True))
    return {"attachments": queue_delete(ids)}


def export_for_user(user_id) -> dict:
    """What the student may download about their files: metadata only (the bytes belong to the module that uses them)."""
    from core.serialization import row_to_dict

    rows = (
        Attachment.objects.filter(user_id=user_id)
        .exclude(status=Attachment.Status.DELETING)
        .order_by("created_at", "id")
    )
    return {"attachments": [row_to_dict(a, exclude=frozenset({"user_id", "bucket", "path"})) for a in rows]}
