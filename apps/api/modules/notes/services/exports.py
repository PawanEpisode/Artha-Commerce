"""
Flattened PDF export (PRD FR-F03-53, ERD 2.10, 6.5): the request, the worker's job and the expiry sweep.

Request: validated options, an idempotent job row per `client_id`, one monthly `exports` charge (refunded when the job fails),
one queued `notes.export_pdf` job. Who may export is the pure rule `domain.export_options.export_block_reason`.

Worker: downloads the original to a temp file (capped), reads the live marks in one pass, calls `worker.export.build_flattened_pdf`
and stores the result as `note_export` through `media`. The ORIGINAL object is only ever read. A failure that retrying cannot
fix ends the job `failed` with an `error_code` and refunds the charge once; an unexpected one is raised so the queue retries,
and the glue calls `give_up` on the last attempt. `options["_suggested_pages"]` carries the page-range hint of `export_too_large`.
"""

from __future__ import annotations

import logging
import os
import tempfile
from dataclasses import dataclass
from datetime import timedelta

from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.exceptions import NotFound

from core import jobs as core_jobs
from modules.media import services as media

from .. import events
from ..domain.export_options import OptionsError, export_block_reason, validate_options
from ..domain.pagespec import format_pages
from ..domain.quota import resets_on
from ..errors import QuotaExceeded
from ..errors_ocr_export import ExportNotAllowed, InvalidOptions
from ..media_kinds import EXPORT_MAX_BYTES, EXPORT_RETENTION_DAYS, PDF_MIME
from ..models import Document, ExportJob, Tag
from ..selectors import exports as export_selectors
from . import objects, quota

logger = logging.getLogger(__name__)

JOB_EXPORT_PDF = "notes.export_pdf"  # same string as `notes.jobs.JOB_EXPORT_PDF`, which imports this package
KIND = "note_export"
SUGGESTION_KEY = "_suggested_pages"  # on the job's options; the serializer turns it into `details.suggested_pages`
EXPIRED_ROW_KEEP_DAYS = 7  # an expired export stays visible as "expired" for a week, then the row goes
BATCH = 200


@dataclass(frozen=True)
class ExportRequest:
    job: ExportJob
    created: bool  # False: a replay of the same `client_id` (200, the stored job)


# --- Request ------------------------------------------------------------------------------------------------------------
def _quota_error(user_id, exc: QuotaExceeded, now) -> QuotaExceeded:
    return QuotaExceeded(extra={**(exc.extra or {}), "kind": "export", "resets_on": resets_on(now).isoformat()})


def request_export(user_id, document_id, options, *, client_id, now=None) -> ExportRequest:
    """
    Queues a flattened export. Raises 404, 422 `export_not_allowed` (details `{reason: restricted|locked|not_ready}`), 422
    `invalid_options` (details `{field}`) and 429 `quota_exceeded` kind `export`. A replayed `client_id` returns the stored job.
    """
    now = now or timezone.now()
    existing = ExportJob.objects.filter(user_id=user_id, client_id=client_id).first()
    if existing is not None:
        return ExportRequest(existing, False)
    document = (
        Document.objects.filter(pk=document_id, user_id=user_id, deleted_at__isnull=True)
        .select_related("content")
        .first()
    )
    if document is None:
        raise NotFound("Document not found.")
    content = document.content
    reason = export_block_reason(
        status=document.status,
        is_encrypted=bool(content and content.is_encrypted),
        page_count=content.page_count if content else document.page_count,
        can_copy=content.can_copy if content else None,
        can_modify=content.can_modify if content else None,
    )
    if reason:
        raise ExportNotAllowed(extra={"reason": reason})
    page_count = content.page_count if content and content.page_count else document.page_count
    try:
        opts = validate_options(options, page_count)
    except OptionsError as exc:
        raise InvalidOptions(str(exc), extra={"field": exc.field}) from exc
    if opts.tags:
        owned = Tag.objects.filter(user_id=user_id, pk__in=opts.tags).count()
        if owned != len(opts.tags):
            raise InvalidOptions("One of those tags does not exist.", extra={"field": "tags"})
    try:
        with transaction.atomic():
            job = ExportJob.objects.create(
                user_id=user_id, kind="pdf", document=document, client_id=client_id, options=opts.stored()
            )
            try:
                quota.charge_monthly(user_id, "exports", 1, now=now)
            except QuotaExceeded as exc:
                raise _quota_error(user_id, exc, now) from exc  # rolls the job row back with the failed charge
            core_jobs.enqueue(JOB_EXPORT_PDF, {"export_id": str(job.id)}, dedupe_key=f"{JOB_EXPORT_PDF}:{job.id}")
    except IntegrityError:  # two replays of one `client_id` raced; the other one won and nothing was charged here
        winner = ExportJob.objects.filter(user_id=user_id, client_id=client_id).first()
        if winner is None:
            raise
        return ExportRequest(winner, False)
    return ExportRequest(job, True)


# --- Worker -------------------------------------------------------------------------------------------------------------
def _fail(job_id, code: str, *, suggestion: str | None = None) -> bool:
    """Ends the job `failed` once (only from queued or running) and refunds its charge. True when this call did it."""
    job = ExportJob.objects.filter(pk=job_id).first()
    if job is None:
        return False
    options = dict(job.options)
    if suggestion:
        options[SUGGESTION_KEY] = suggestion
    changed = ExportJob.objects.filter(pk=job_id, status__in=["queued", "running"]).update(
        status="failed", error_code=code, options=options, updated_at=timezone.now()
    )
    if changed and job.kind == "pdf":
        quota.refund_monthly(job.user_id, "exports", 1, now=job.created_at)  # the month the charge was made in
    return bool(changed)


def _progress(job_id, value: int) -> None:
    ExportJob.objects.filter(pk=job_id, status="running").update(progress=value, updated_at=timezone.now())


def run_pdf_export(export_id) -> dict:
    """The `notes.export_pdf` handler body. Idempotent: a finished, failed or expired job is left as it is."""
    from ..worker import export as engine  # lazy: PDF libraries and fonts belong to the worker process
    from ..worker import pdfutil

    job = ExportJob.objects.select_related("document__content", "document__attachment").filter(pk=export_id).first()
    if job is None or job.status not in ("queued", "running") or job.document is None:
        return {"skipped": True}
    ExportJob.objects.filter(pk=job.pk).update(status="running", progress=5, updated_at=timezone.now())
    document, content = job.document, job.document.content
    reason = export_block_reason(
        status=document.status,
        is_encrypted=bool(content and content.is_encrypted),
        page_count=content.page_count if content else document.page_count,
        can_copy=content.can_copy if content else None,
        can_modify=content.can_modify if content else None,
    )
    if reason in ("locked", "restricted"):
        _fail(job.id, reason)
        return {"failed": reason}
    if reason:
        raise RuntimeError("The document is not ready.")  # not an end state: the queue retries
    options = validate_options({k: v for k, v in job.options.items() if k != SUGGESTION_KEY}, content.page_count)
    marks = export_selectors.marks_for_export(job.user_id, document.id, options)
    with tempfile.TemporaryDirectory(prefix="export-") as tmp:
        source, out = os.path.join(tmp, "source.pdf"), os.path.join(tmp, "out.pdf")
        try:
            objects.download_to(source, document.attachment, limit=content.bytes or document.bytes)
        except objects.SourceTooLarge:
            _fail(job.id, "export_too_large")
            return {"failed": "export_too_large"}
        _progress(job.id, 25)
        core_jobs.heartbeat()
        try:
            result = engine.build_flattened_pdf(
                source,
                marks,
                out,
                pages=options.pages,
                include=options.include,
                appendix=options.appendix,
            )
        except engine.ExportTooLarge as exc:
            hint = exc.suggested_range
            _fail(job.id, "export_too_large", suggestion=format_pages(range(hint[0], hint[1] + 1)) if hint else None)
            return {"failed": "export_too_large"}
        except engine.ExportNotAllowed:
            _fail(job.id, "restricted")
            return {"failed": "restricted"}
        except pdfutil.PdfPasswordRequired:
            _fail(job.id, "locked")
            return {"failed": "locked"}
        except pdfutil.PdfOpenError:
            _fail(job.id, "failed")
            return {"failed": "failed"}
        _progress(job.id, 80)
        core_jobs.heartbeat()
        if os.path.getsize(out) > EXPORT_MAX_BYTES:
            _fail(job.id, "export_too_large")
            return {"failed": "export_too_large"}
        with open(out, "rb") as handle:
            attachment = media.store_generated(job.user_id, KIND, mime=PDF_MIME, data=handle.read())
    finished = timezone.now()
    done = ExportJob.objects.filter(pk=job.pk, status="running").update(
        status="done",
        progress=100,
        page_count=result.page_count,
        attachment=attachment,
        error_code=None,
        expires_at=finished + timedelta(days=EXPORT_RETENTION_DAYS),
        updated_at=finished,
    )
    if not done:  # failed or expired while we were building: the file is not wanted
        media.queue_delete([attachment.id])
        return {"skipped": True}
    events.announce_export_ready(job.user_id, job.id, kind="pdf", document_id=document.id, page_count=result.page_count)
    return {"pages": result.page_count, "marks": result.marks_drawn, "skipped_marks": len(result.skipped)}


def give_up(export_id) -> dict:
    """The queue gave up on the job (attempts used): it ends `failed` and the student gets the charge back."""
    return {"failed": _fail(export_id, "failed")}


# --- Expiry (light job, runs in the tick) ---------------------------------------------------------------------------------
def expire_exports(*, now=None) -> dict:
    """
    Finished exports past their retention become `expired` and their files are queued for deletion through `media`; expired and
    failed rows older than `EXPIRED_ROW_KEEP_DAYS` beyond the retention are removed. Re-entrant: each call handles a batch.
    """
    now = now or timezone.now()
    due = list(
        ExportJob.objects.filter(status="done", expires_at__lte=now)
        .order_by("expires_at")
        .values_list("id", "attachment_id")[:BATCH]
    )
    attachment_ids = [a for _, a in due if a]
    with transaction.atomic():
        ExportJob.objects.filter(pk__in=[i for i, _ in due], status="done").update(status="expired", updated_at=now)
        media.queue_delete(attachment_ids)
    old = now - timedelta(days=EXPORT_RETENTION_DAYS + EXPIRED_ROW_KEEP_DAYS)
    stale = list(
        ExportJob.objects.filter(status__in=["expired", "failed"], created_at__lt=old).values_list("id", flat=True)[
            :BATCH
        ]
    )
    removed = ExportJob.objects.filter(pk__in=stale).delete()[0] if stale else 0
    return {"expired": len(due), "removed": removed}
