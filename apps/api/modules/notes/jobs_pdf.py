"""
Handlers of the PDF pipeline (ERD 6.5), registered by `notes.jobs.register_handlers`. The two heavy ones run only in the worker;
the expiry job is light and runs from the tick. Each handler is idempotent: a replay, a reclaimed job or a second document of
the same bytes finds the work done and does nothing.

    notes.inspect               download the stored object (capped), `worker.inspect.inspect_pdf`, then in one transaction:
                                reject (`rejected` + reason + quota back), `needs_password`, or find-or-create the shared
                                `FileContent` by SHA-256, point the document at it and mark it `ready`; afterwards the
                                cover thumbnail (a `note_image` attachment through `media`) and the extraction job.
    notes.extract_text          native text in chunks of 20 pages into `FilePage` under the rank rule (`services.file_pages`),
                                vectors per page, `text_pages_done` growing only. One job loops through the chunks inside a
                                time budget with a heartbeat between them, then chains the next job from the page it reached.
    notes.expire_reservations   uploads never confirmed become `expired` and free their quota; old expired rows and trash go.

Failure rules: storage trouble raises (the queue retries with backoff). A parser that blows up is retried too; on the LAST
attempt the document becomes `failed` (reason `decode_failed`) and keeps its quota until the student deletes it. A file the
inspection judges unusable is `rejected` at once, with the reason the student sees. Nothing here logs file names, titles or text.
"""

from __future__ import annotations

import logging
import os
import tempfile
import time
from typing import TYPE_CHECKING

from django.db import IntegrityError, transaction
from django.utils import timezone

from core import jobs as core_jobs
from core.storage import StorageError
from modules.media import services as media
from modules.media.errors import StorageUnavailable
from modules.media.models import Attachment

from . import events
from .errors import QuotaExceeded
from .jobs import JOB_EXTRACT_TEXT, JOB_INSPECT
from .models import Document, FileContent
from .services import content as content_service
from .services import document_trash, documents, file_pages, objects, quota, search_index

if TYPE_CHECKING:
    from .worker import inspect as pdf_inspect

logger = logging.getLogger(__name__)

JOB_EXPIRE_DOCUMENTS = "notes.expire_reservations"
CHUNK_PAGES = 20  # worker.extract.DEFAULT_CHUNK; imported only when a job runs, so the API starts without PDFium
EXTRACT_BUDGET_SECONDS = 150  # one job's share; the next chunk of a long file is a new job
INSPECT_REASONS = frozenset({"type_mismatch", "pdf_corrupt", "too_many_pages", "decode_failed", "policy"})
Status = Document.Status
TextStatus = FileContent.TextStatus


def _last_attempt() -> bool:
    job = core_jobs.current_job()
    return job is not None and job.attempts >= job.max_attempts


# --- Inspect ---------------------------------------------------------------------------------------------------------------------
def inspect_job(payload: dict) -> dict:
    document = Document.objects.select_related("attachment").filter(pk=payload["document_id"]).first()
    if document is None:
        return {"skipped": "gone"}
    if document.status not in (Status.INSPECTING, Status.FAILED):
        return {"skipped": document.status}  # done already, or not clean yet (the on_clean hook queues this job again)
    attachment = document.attachment
    if attachment.status != Attachment.Status.CLEAN:
        return {"skipped": "not_clean"}
    try:
        with tempfile.TemporaryDirectory(prefix="inspect-") as tmp:
            path = os.path.join(tmp, "source.pdf")
            try:
                objects.download_to(path, attachment, limit=attachment.bytes)
            except objects.SourceTooLarge:
                return _settle(document.pk, None, reject="too_large")
            from .worker import inspect as pdf_inspect  # PDF libraries belong to the worker process

            result = pdf_inspect.inspect_pdf(path)
    except objects.SourceMissing:
        raise  # storage trouble: retried with backoff
    except Exception:
        if _last_attempt():
            _mark_failed(document.pk)
        raise
    return _settle(document.pk, result)


def _mark_failed(document_id) -> None:
    Document.objects.filter(pk=document_id, status__in=[Status.INSPECTING, Status.FAILED]).update(
        status=Status.FAILED, status_reason="decode_failed", updated_at=timezone.now()
    )


def _find_or_create_content(result: pdf_inspect.InspectResult) -> FileContent:
    """The shared derived row of these bytes. A second student with the same file copies nothing: they point at it."""
    existing = FileContent.objects.select_for_update().filter(sha256=result.sha256).first()
    if existing is not None:
        if existing.page_meta is None and not result.needs_password:
            _fill(existing, result)
        content_service.clear_orphaned(existing.pk)
        return existing
    try:
        with transaction.atomic():
            content = FileContent(sha256=result.sha256, bytes=result.bytes or 0)
            _fill(content, result)
            return content
    except IntegrityError:  # another worker created it a moment ago
        return FileContent.objects.select_for_update().get(sha256=result.sha256)


def _fill(content: FileContent, result: pdf_inspect.InspectResult) -> None:
    content.is_encrypted = result.is_encrypted
    if result.needs_password:
        content.text_status = TextStatus.LOCKED  # nothing is read without the password (it is typed in the browser)
    else:
        content.page_count = result.page_count
        content.page_meta = list(result.page_meta)
        content.outline = list(result.outline)
        content.can_copy, content.can_modify = result.can_copy, result.can_modify
        content.has_javascript = result.has_javascript
        content.is_scanned, content.text_pct = result.is_scanned, result.text_pct
    content.save()


def _settle(document_id, result: pdf_inspect.InspectResult | None, reject: str | None = None) -> dict:
    """Applies the inspection to the document under its row lock. Returns what the job reports (counts and codes, no text)."""
    cover: bytes | None = None
    with transaction.atomic():
        document = Document.objects.select_for_update().filter(pk=document_id).first()
        if document is None or document.status not in (Status.INSPECTING, Status.FAILED):
            return {"skipped": "changed"}
        reason = reject or _verdict(document, result)
        if reason:
            documents.reject_stored(document, reason)
            return {"rejected": reason}
        if result.needs_password:
            document.content = _find_or_create_content(result)
            document.status, document.status_reason = Status.NEEDS_PASSWORD, None
            document.save(update_fields=["content", "status", "status_reason", "updated_at"])
            return {"status": "needs_password"}
        content = _find_or_create_content(result)
        document.content, document.page_count = content, content.page_count
        document.status, document.status_reason = Status.READY, None
        document.save(update_fields=["content", "page_count", "status", "status_reason", "updated_at"])
        cover = result.cover_webp
        wants_text = content.text_status == TextStatus.PENDING
        searchable = content.text_status == TextStatus.DONE
        replaces = document.replaces_document_id is not None
    if cover:
        _attach_cover(document_id, cover)
    _announce(document, content, "readable")
    if wants_text:
        core_jobs.enqueue(
            JOB_EXTRACT_TEXT,
            {"content_id": str(content.pk), "document_id": str(document_id)},
            dedupe_key=f"{JOB_EXTRACT_TEXT}:{content.pk}",
        )
    elif searchable:
        _announce(document, content, "searchable")
    if replaces:
        from .services import reanchor  # local: it imports services that import this module

        reanchor.queue_reanchor(document)
    return {"status": "ready", "pages": content.page_count, "shared": not wants_text}


def _verdict(document: Document, result: pdf_inspect.InspectResult) -> str | None:
    """The reason to reject, or None. Plan limits apply to uploads only: a platform file is ours."""
    if not result.ok:
        return result.error_code if result.error_code in INSPECT_REASONS else "policy"
    if document.origin != Document.Origin.UPLOAD or result.needs_password:
        return None
    if result.bytes is not None and result.bytes > document.attachment.bytes:
        return "too_large"  # more bytes than were reserved: the quota taken for it would be a lie
    if result.page_count and result.page_count > quota.max_pages(document.user_id):
        return "too_many_pages"
    return None


def _announce(document: Document, content: FileContent, stage: str) -> None:
    events.announce_document_ready(
        document.user_id,
        document.pk,
        pages=content.page_count,
        scanned=content.is_scanned,
        encrypted=content.is_encrypted,
        stage=stage,
    )


def _attach_cover(document_id, webp: bytes) -> None:
    """
    The first page as a 240 px `note_image`, through `media` like any image (quota, scan, signed reads). Best effort: a student
    at the storage limit or a storage hiccup only means no thumbnail. A replayed job never adds a second one.
    """
    document = Document.objects.filter(pk=document_id).first()
    if document is None or document.cover_attachment_id:
        return
    attachment = None
    try:
        upload = media.create_upload(document.user_id, "note_image", mime="image/webp", bytes=len(webp))
        attachment = upload.attachment
        media.get_storage().upload(
            attachment.bucket, attachment.path, webp, content_type="image/webp", cache_control="3600"
        )
        media.complete_upload(document.user_id, attachment.pk)
        Document.objects.filter(pk=document_id, cover_attachment__isnull=True).update(cover_attachment=attachment)
    except (QuotaExceeded, StorageError, StorageUnavailable) as exc:
        logger.info("No cover for a document: %s", type(exc).__name__)
        if attachment is not None:
            media.queue_delete([attachment.pk])
    except Exception as exc:  # noqa: BLE001 - a thumbnail must never fail the inspection that already succeeded
        logger.warning("Cover failed: %s", type(exc).__name__)
        if attachment is not None:
            media.queue_delete([attachment.pk])


# --- Extract -----------------------------------------------------------------------------------------------------------------------
def _source(content: FileContent, hint) -> Document | None:
    """A document of anyone that still holds these bytes (the one that queued the job first)."""
    live = (
        Document.objects.filter(content_id=content.pk, attachment__status=Attachment.Status.CLEAN)
        .exclude(status__in=[Status.REJECTED, Status.EXPIRED])
        .select_related("attachment")
    )
    if hint:
        preferred = live.filter(pk=hint).first()
        if preferred is not None:
            return preferred
    return live.order_by("created_at").first()


def _set_text_status(content_id, status: str) -> None:
    FileContent.objects.filter(pk=content_id).update(text_status=status, updated_at=timezone.now())


def extract_text_job(payload: dict) -> dict:
    content = FileContent.objects.filter(pk=payload["content_id"]).first()
    if content is None:
        return {"skipped": "gone"}
    if content.text_status in (TextStatus.DONE, TextStatus.SKIPPED):
        return {"skipped": content.text_status}
    if content.is_encrypted and content.page_count is None:
        _set_text_status(content.pk, TextStatus.LOCKED)
        return {"skipped": "locked"}
    if not content.page_count:
        return {"skipped": "no_pages"}
    source = _source(content, payload.get("document_id"))
    if source is None:
        return {"skipped": "no_document"}  # everyone deleted it; the content is orphaned and will be purged
    start = int(payload.get("from") or content.text_pages_done + 1)
    if content.text_status in (TextStatus.PENDING, TextStatus.FAILED):
        _set_text_status(content.pk, TextStatus.RUNNING)
    try:
        return _extract(content, source, start, payload)
    except Exception:
        if _last_attempt():
            _set_text_status(content.pk, TextStatus.FAILED)
        raise


def _extract(content: FileContent, source: Document, start: int, payload: dict) -> dict:
    from .worker import extract  # PDF libraries belong to the worker process
    from .worker.pdfutil import PdfOpenError, PdfPasswordRequired

    deadline = time.monotonic() + EXTRACT_BUDGET_SECONDS
    page, total, blank = start, content.page_count, 0
    with tempfile.TemporaryDirectory(prefix="extract-") as tmp:
        path = os.path.join(tmp, "source.pdf")
        objects.download_to(path, source.attachment, limit=content.bytes)
        while page <= total:
            last = min(page + CHUNK_PAGES - 1, total)
            try:
                pages = extract.extract_pages(path, page, last)
            except PdfPasswordRequired:
                _set_text_status(content.pk, TextStatus.LOCKED)
                return {"locked": True}
            except PdfOpenError:
                _set_text_status(content.pk, TextStatus.FAILED)
                return {"failed": "unreadable"}
            writes = [file_pages.PageWrite(p.page, p.text) for p in pages]
            blank += sum(1 for p in pages if p.error)
            file_pages.upsert_pages(content.pk, writes)
            search_index.refresh_pages(content.pk, [w.page for w in writes])
            file_pages.record_text_progress(content.pk, last)
            if not core_jobs.heartbeat() and core_jobs.current_job() is not None:
                return {"stopped": "lock lost", "reached": last}
            page = last + 1
            if page <= total and time.monotonic() > deadline:
                core_jobs.enqueue(
                    JOB_EXTRACT_TEXT,
                    {"content_id": str(content.pk), "document_id": payload.get("document_id"), "from": page},
                    dedupe_key=f"{JOB_EXTRACT_TEXT}:{content.pk}:{page}",
                )
                return {"chained": page}
    _set_text_status(content.pk, TextStatus.DONE)
    content.refresh_from_db()
    _announce_searchable(content)
    return {"done": True, "pages": total, "unreadable_pages": blank}


def _announce_searchable(content: FileContent) -> None:
    """`searchable` for every document of these bytes, unless OCR is what will make a scanned file searchable."""
    for document in Document.objects.filter(content_id=content.pk, deleted_at__isnull=True, status=Status.READY):
        ocr_wanted = bool(content.is_scanned) and (
            content.ocr_status in ("pending", "running", "partial") or document.ocr_mode != "none"
        )
        if not ocr_wanted:
            _announce(document, content, "searchable")


# --- Housekeeping ----------------------------------------------------------------------------------------------------------------------
def expire_documents_job(payload: dict) -> dict:
    """Uploads nobody confirmed are released, then trash past its 30 days and old expired rows are purged (light, from the tick)."""
    expired = document_trash.expire_reservations()
    purged = document_trash.purge_expired()
    return {"expired": expired, "purged": purged}


def register_handlers(jobs_module) -> None:
    jobs_module.register_handler(JOB_INSPECT, inspect_job)
    jobs_module.register_handler(JOB_EXTRACT_TEXT, extract_text_job)
    jobs_module.register_handler(JOB_EXPIRE_DOCUMENTS, expire_documents_job)
