"""
Resumable upload of a big PDF (PRD FR-F03-31): the file goes to storage in parts straight from the browser, and a part that
failed is sent again without restarting the file.

How it works
- The reservation is unchanged (quota, limits, scan and inspection are the ordinary upload's). For a big file it also says
  `resumable: {document_id, part_size, parts}` when this deployment can do it (S3 credentials set, flag `notes_ai` on).
- `start` opens an S3 multipart upload on the same object path (or finds the open one) and answers with the parts already
  stored, so a retry or a second tab continues where the first stopped. `sign_parts` returns one short-lived URL per part,
  `finish` completes the multipart upload from the browser's list of ETags (checked against what storage holds), and the
  ordinary `complete` then confirms the object like for a single PUT.
- Aborting or letting the reservation expire aborts the multipart upload, so no half-file stays in the bucket.
"""

from __future__ import annotations

import logging
import math

from django.db import transaction

from core.feature_flags import flag_enabled
from core.s3 import Part, get_s3
from core.storage import StorageError
from modules.media.errors import StorageUnavailable
from modules.media.models import Attachment

from ..errors_resumable import NotResumable, PartsIncomplete, ResumableUnavailable
from ..models import Document
from . import documents

logger = logging.getLogger(__name__)

MIB = 1024 * 1024
PART_SIZE = 8 * MIB  # S3 needs at least 5 MiB for every part but the last
MIN_BYTES = 16 * MIB  # smaller files are quicker as one PUT
MAX_PARTS = 10_000
SIGN_AT_ONCE = 20
URL_SECONDS = 3600


def available() -> bool:
    return get_s3() is not None


def hint(user_id, document: Document) -> dict | None:
    """What the reservation answer adds for a file that can be sent in parts, else None (an ordinary single PUT)."""
    if document.bytes < MIN_BYTES or not available() or not flag_enabled("notes_ai", user_id, strict=True):
        return None
    parts = math.ceil(document.bytes / PART_SIZE)
    if parts > MAX_PARTS:
        return None
    return {"document_id": str(document.id), "part_size": PART_SIZE, "parts": parts}


def _s3():
    client = get_s3()
    if client is None:
        raise ResumableUnavailable
    return client


def _waiting(user_id, document_id) -> tuple[Document, Attachment]:
    document = documents.get_locked(user_id, document_id)
    attachment = Attachment.objects.select_related().get(pk=document.attachment_id)
    if (
        document.status != Document.Status.RESERVED
        or attachment.status != Attachment.Status.RESERVED
        or document.bytes < MIN_BYTES
    ):
        raise NotResumable
    return document, attachment


def _part_count(attachment: Attachment) -> int:
    return math.ceil(attachment.bytes / PART_SIZE)


@transaction.atomic
def start(user_id, document_id) -> dict:
    """Opens the multipart upload (once) and says which parts storage already holds. Safe to call again and again."""
    s3 = _s3()
    document, attachment = _waiting(user_id, document_id)
    try:
        if not document.resumable_upload_id:
            document.resumable_upload_id = s3.create_multipart(attachment.bucket, attachment.path, attachment.mime)
            document.save(update_fields=["resumable_upload_id", "updated_at"])
            done: list[Part] = []
        else:
            done = s3.list_parts(attachment.bucket, attachment.path, document.resumable_upload_id)
    except StorageError as exc:
        logger.warning("Multipart start failed: %s", exc)
        raise StorageUnavailable from exc
    return {
        "part_size": PART_SIZE,
        "parts": _part_count(attachment),
        "done": [{"number": p.number, "etag": p.etag, "size": p.size} for p in done],
    }


def sign_parts(user_id, document_id, numbers: list[int]) -> list[dict]:
    """One URL per requested part (a PUT with the part's bytes as the body; the answer's `ETag` header goes to `finish`)."""
    s3 = _s3()
    with transaction.atomic():
        document, attachment = _waiting(user_id, document_id)
    if not document.resumable_upload_id:
        raise NotResumable
    total = _part_count(attachment)
    wanted = sorted({n for n in numbers if 1 <= n <= total})[:SIGN_AT_ONCE]
    return [
        {
            "number": n,
            "url": s3.presign_part(
                attachment.bucket, attachment.path, document.resumable_upload_id, n, expires=URL_SECONDS
            ),
        }
        for n in wanted
    ]


def _expected_size(attachment: Attachment, number: int) -> int:
    return min(PART_SIZE, attachment.bytes - (number - 1) * PART_SIZE)


@transaction.atomic
def finish(user_id, document_id, numbers: list[int]) -> dict:
    """
    Joins the parts into the object. The browser only says which part numbers it sent; the ETags and sizes are what STORAGE
    holds, so a part that never arrived or arrived short is 422 `parts_incomplete` and nothing is joined.
    """
    s3 = _s3()
    document, attachment = _waiting(user_id, document_id)
    if not document.resumable_upload_id:
        raise NotResumable
    total = _part_count(attachment)
    if set(numbers) != set(range(1, total + 1)):
        raise PartsIncomplete
    try:
        held = {p.number: p for p in s3.list_parts(attachment.bucket, attachment.path, document.resumable_upload_id)}
        if any(n not in held or held[n].size != _expected_size(attachment, n) for n in range(1, total + 1)):
            raise PartsIncomplete
        s3.complete_multipart(
            attachment.bucket,
            attachment.path,
            document.resumable_upload_id,
            [held[n] for n in range(1, total + 1)],
        )
    except StorageError as exc:
        logger.warning("Multipart complete failed: %s", exc)
        raise StorageUnavailable from exc
    document.resumable_upload_id = None
    document.save(update_fields=["resumable_upload_id", "updated_at"])
    return {"joined": total}


def abort_quietly(document: Document) -> None:
    """Best effort when an upload is cancelled or expires: a leftover multipart upload costs storage, never correctness."""
    upload_id = document.resumable_upload_id
    client = get_s3()
    if not upload_id or client is None:
        return
    try:
        attachment = Attachment.objects.get(pk=document.attachment_id)
        client.abort_multipart(attachment.bucket, attachment.path, upload_id)
    except (StorageError, Attachment.DoesNotExist) as exc:
        logger.info("Multipart abort skipped: %s", type(exc).__name__)
    Document.objects.filter(pk=document.pk).update(resumable_upload_id=None)
