"""
State changes every AI job shares (summary now, page reading next): refunds, cancel, discard, expiry, and the cleanup when a
student withdraws consent. The monthly quota is charged in the request's transaction (`services.quota.charge_monthly`, one
conditional statement); a job that fails, is cancelled or is blocked gives it back here, once (`charged` flips to false).
"""

from __future__ import annotations

from datetime import datetime

from django.db import transaction
from django.utils import timezone

from ..errors_ai import NotCancellable
from ..models import AiJob
from . import quota

COUNTER = {"exam_summary": "ai_summaries", "ocr_page_ai": "ai_ocr_pages"}


def charge_amount(job: AiJob) -> int:
    """What the job still holds: one summary, or the pages of an AI read that were not already given back page by page."""
    if job.kind == "ocr_page_ai":
        return max(0, len(job.scope.get("pages") or []) - len(job.scope.get("refunded_pages") or []))
    return 1


def refund_pages(job: AiJob, pages: list[int]) -> None:
    """Gives back the price of pages that could not be read, once each. The caller holds the row lock and saves the job."""
    already = set(job.scope.get("refunded_pages") or [])
    fresh = [p for p in pages if p in set(job.scope.get("pages") or []) and p not in already]
    if not fresh or not job.charged:
        return
    quota.refund_monthly(job.user_id, COUNTER[job.kind], len(fresh), now=job.created_at)
    job.scope = {**job.scope, "refunded_pages": sorted(already | set(fresh))}


def refund(job: AiJob) -> None:
    """Gives the charge back once (inside the caller's transaction, job row locked or freshly created)."""
    if not job.charged:
        return
    amount = charge_amount(job)
    if amount:
        quota.refund_monthly(job.user_id, COUNTER[job.kind], amount, now=job.created_at)
    job.charged = False
    if job.kind == "ocr_page_ai":
        job.scope = {**job.scope, "refunded_pages": sorted(job.scope.get("pages") or [])}


def clear_draft(job: AiJob) -> None:
    job.result_md = None
    job.result_json = None


def close(
    job: AiJob, status: str, *, error: str | None = None, refunded: bool = False, now: datetime | None = None
) -> None:
    """Ends a job: status, optional error code, optional refund, the draft cleared. The caller holds the row lock."""
    if refunded:
        refund(job)
    job.status = status
    job.error_code = error
    job.finished_at = now or timezone.now()
    clear_draft(job)
    job.save()


def lock(user_id, job_id) -> AiJob | None:
    return AiJob.objects.select_for_update().filter(pk=job_id, user_id=user_id).first()


@transaction.atomic
def cancel(user_id, job_id) -> AiJob | None:
    """Queued only (refunded). Already cancelled is fine; running is 409 (the model call cannot be taken back)."""
    job = lock(user_id, job_id)
    if job is None:
        return None
    if job.status == AiJob.Status.CANCELLED:
        return job
    if job.status != AiJob.Status.QUEUED:
        raise NotCancellable
    close(job, AiJob.Status.CANCELLED, refunded=True)
    return job


@transaction.atomic
def discard(user_id, job_id) -> AiJob | None:
    """Throws a ready draft away (nothing is refunded: the model ran). Idempotent; other states are left as they are."""
    job = lock(user_id, job_id)
    if job is None:
        return None
    if job.status == AiJob.Status.READY:
        close(job, AiJob.Status.DISCARDED)
    return job


def discard_all_for_user(user_id) -> dict:
    """Consent withdrawn: drafts go, queued jobs are cancelled and refunded. A running job checks consent again before it
    stores anything (see `services.summary.run_summary`)."""
    drafts = cancelled = 0
    with transaction.atomic():
        for job in AiJob.objects.select_for_update().filter(user_id=user_id, status__in=["ready", "queued"]):
            if job.status == AiJob.Status.READY:
                close(job, AiJob.Status.DISCARDED)
                drafts += 1
            else:
                close(job, AiJob.Status.CANCELLED, error="consent_withdrawn", refunded=True)
                cancelled += 1
    return {"drafts_deleted": drafts, "requests_cancelled": cancelled}


def expire_drafts(*, now: datetime | None = None, limit: int = 200) -> int:
    """Light job (the tick): drafts past their 14 days are deleted. Returns how many."""
    now = now or timezone.now()
    ids = list(AiJob.objects.filter(status="ready", expires_at__lte=now).values_list("pk", flat=True)[:limit])
    done = 0
    for pk in ids:
        with transaction.atomic():
            job = AiJob.objects.select_for_update().filter(pk=pk, status="ready").first()
            if job is not None:
                close(job, AiJob.Status.EXPIRED, now=now)
                done += 1
    return done
