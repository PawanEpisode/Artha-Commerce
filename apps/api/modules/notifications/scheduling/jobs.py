"""
Exact-time jobs (ERD 2.6): plan one when an event starts a countdown, cancel it when the countdown is replaced, fire it
when the moment comes. All writes live here.

Reliability rules:
  * `plan_timer_end` is an upsert on the unique key (student, kind, timer, version): replaying an event plans nothing new.
  * Publishing to the queue happens after the row exists and never raises into the caller (a student's write must not
    fail because a queue is down). A job whose message never arrived is fired by the sweep.
  * `fire_job` claims the row with one conditional UPDATE (`pending` to `fired`). Only the caller that updated one row
    goes on, so a queue retry racing the sweep cannot send twice (FR-N17).
  * After the claim, a failure that may pass puts the job back to `pending` (up to `MAX_ATTEMPTS`) and answers with a
    retryable error; a skip is recorded with its reason and answered normally so the queue does not retry it.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from django.db import transaction
from django.db.models import F
from django.utils import timezone

from .. import flags, handlers
from ..domain.enums import JobKind, JobStatus, SkipReason, SuppressReason
from ..domain.policy import Action
from ..errors import TransientJobError
from ..logs import log_event
from ..models import ScheduledJob
from ..services import notify as notify_service
from . import queue

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 3


# --- Planning ------------------------------------------------------------------------------------------------------
def plan_timer_end(
    user_id,
    *,
    client_id,
    version: int,
    fire_at: datetime,
    context: Mapping[str, Any],
) -> ScheduledJob:
    """
    The job that will tell the student their round (or break) ended, for this exact timer version. Idempotent: the same
    version returns the same row. A job that is already past `pending` is returned untouched and nothing is published.
    """
    with transaction.atomic():
        job, created = ScheduledJob.objects.select_for_update().get_or_create(
            user_id=user_id,
            kind=JobKind.TIMER_END,
            subject_key=str(client_id),
            expected_version=version,
            defaults={"fire_at": fire_at, "context": dict(context)},
        )
        if not created and job.status == JobStatus.PENDING and job.fire_at != fire_at:
            _forget_message(job.external_id)
            job.fire_at, job.context, job.external_id = fire_at, dict(context), None
            job.save(update_fields=["fire_at", "context", "external_id", "updated_at"])
    if job.status == JobStatus.PENDING and job.external_id is None:
        _publish(job)
    return job


def _publish(job: ScheduledJob) -> None:
    try:
        external_id = queue.get_queue().publish(job.id, job.fire_at)
    except Exception as exc:  # noqa: BLE001 - the student's request must not fail; the sweep will fire the job
        log_event(logging.WARNING, "job_publish_failed", kind=job.kind, error_type=type(exc).__name__)
        return
    ScheduledJob.objects.filter(pk=job.pk, status=JobStatus.PENDING).update(
        external_id=external_id, updated_at=timezone.now()
    )
    job.external_id = external_id


def _forget_message(external_id: str | None) -> None:
    if not external_id:
        return
    try:
        queue.get_queue().cancel(external_id)
    except Exception as exc:  # noqa: BLE001 - a courtesy only: a superseded job is skipped when it fires anyway
        log_event(logging.WARNING, "job_cancel_failed", error_type=type(exc).__name__)


def cancel_for_timer(user_id, *, keep: tuple[object, int] | None = None) -> int:
    """
    Cancel the student's pending timer jobs, except `keep` (client id and version of the one that stays). A new version
    supersedes the old one, and an ended, paused or discarded timer cancels everything. Returns how many were cancelled.
    """
    pending = ScheduledJob.objects.filter(user_id=user_id, kind=JobKind.TIMER_END, status=JobStatus.PENDING)
    if keep is not None:
        pending = pending.exclude(subject_key=str(keep[0]), expected_version=keep[1])
    rows = list(pending.values_list("id", "external_id"))
    if not rows:
        return 0
    ids = [job_id for job_id, _ in rows]
    ScheduledJob.objects.filter(id__in=ids, status=JobStatus.PENDING).update(
        status=JobStatus.CANCELLED, updated_at=timezone.now()
    )
    for _, external_id in rows:
        _forget_message(external_id)
    return len(rows)


# --- Firing --------------------------------------------------------------------------------------------------------
class FireOutcome(StrEnum):
    NOTIFIED = "notified"  # a notification was created and handed to dispatch (its own outcome is in `delivery`)
    SKIPPED = "skipped"  # claimed, judged, nothing to send
    IGNORED = "ignored"  # the job is gone, or another call already claimed it


@dataclass(frozen=True)
class FireResult:
    outcome: FireOutcome
    reason: str | None = None
    delivery: str | None = None  # `sent`, `suppressed`, `deferred`, `failed` or `already_sent`


def _claim(job_id, now: datetime) -> ScheduledJob | None:
    """The atomic claim (FR-N17). One UPDATE decides the winner; everyone else updates zero rows."""
    won = ScheduledJob.objects.filter(pk=job_id, status=JobStatus.PENDING).update(
        status=JobStatus.FIRED, fired_at=now, attempts=F("attempts") + 1, updated_at=timezone.now()
    )
    return ScheduledJob.objects.filter(pk=job_id).first() if won == 1 else None


def _overdue_ms(job: ScheduledJob, now: datetime) -> int:
    return int((now - job.fire_at).total_seconds() * 1000)


def _skip(job: ScheduledJob, reason: SkipReason, now: datetime) -> FireResult:
    ScheduledJob.objects.filter(pk=job.pk).update(
        status=JobStatus.SKIPPED, skip_reason=reason, updated_at=timezone.now()
    )
    log_event(logging.INFO, "job_skipped", kind=job.kind, reason=reason.value, overdue_ms=_overdue_ms(job, now))
    return FireResult(FireOutcome.SKIPPED, reason=reason.value)


def _release(job: ScheduledJob) -> None:
    """Back to `pending` for the next attempt, or `failed` once the attempts are used up."""
    claimed = ScheduledJob.objects.filter(pk=job.pk, status=JobStatus.FIRED)
    if job.attempts >= MAX_ATTEMPTS:
        claimed.update(status=JobStatus.FAILED, updated_at=timezone.now())
        log_event(logging.ERROR, "job_failed", kind=job.kind, attempts=job.attempts)
    else:
        claimed.update(status=JobStatus.PENDING, fired_at=None, updated_at=timezone.now())


def fire_job(job_id: UUID | str, *, now: datetime | None = None) -> FireResult:
    """
    Fire one job. Safe to call any number of times, from any number of workers: the first caller claims the job, the
    others see it is taken and do nothing. Raises `TransientJobError` when the work should be retried.
    """
    now = now or timezone.now()
    job = _claim(job_id, now)
    if job is None:
        known = ScheduledJob.objects.filter(pk=job_id).exists()
        log_event(logging.INFO, "job_skipped", reason="not_pending" if known else "gone")
        return FireResult(FireOutcome.IGNORED, reason="not_pending" if known else "gone")
    try:
        return _process(job, now)
    except TransientJobError:
        _release(job)
        raise
    except handlers.UnknownJobKind:
        ScheduledJob.objects.filter(pk=job.pk).update(status=JobStatus.FAILED, updated_at=timezone.now())
        log_event(logging.ERROR, "job_failed", kind=job.kind, reason="unknown_kind")
        return FireResult(FireOutcome.SKIPPED, reason="unknown_kind")
    except Exception as exc:
        logger.exception("Job %s failed on attempt %s", job.id, job.attempts)
        _release(job)
        raise TransientJobError() from exc


def _process(job: ScheduledJob, now: datetime) -> FireResult:
    handler = handlers.get(job.kind)
    event_key = handler.event_key(job)
    if not flags.master_enabled() or flags.event_disabled(event_key):
        return _skip(job, SkipReason.DISABLED, now)
    if not flags.send_flag_enabled(job.user_id):
        return _skip(job, SkipReason.FLAG_OFF, now)

    verdict = handler.judge(job, now)
    if isinstance(verdict, handlers.Skip):
        return _skip(job, verdict.reason, now)
    if isinstance(verdict, handlers.NotYet):
        raise TransientJobError("The moment has not arrived yet.")

    sent = notify_service.notify(
        job.user_id,
        verdict.event_key,
        context=verdict.context,
        dedupe_ref=verdict.dedupe_parts,
        now=now,
        intended_at=job.fire_at,
    )
    result = sent.dispatch
    if result.action is Action.SUPPRESS and result.reason is SuppressReason.STALE:
        ScheduledJob.objects.filter(pk=job.pk).update(
            status=JobStatus.SKIPPED, skip_reason=SkipReason.STALE, updated_at=timezone.now()
        )
        log_event(logging.INFO, "job_skipped", kind=job.kind, reason="stale", overdue_ms=_overdue_ms(job, now))
        return FireResult(FireOutcome.SKIPPED, reason=SkipReason.STALE.value, delivery=result.outcome)
    log_event(logging.INFO, "job_fired", kind=job.kind, event=verdict.event_key, overdue_ms=_overdue_ms(job, now))
    return FireResult(FireOutcome.NOTIFIED, delivery=result.outcome)
