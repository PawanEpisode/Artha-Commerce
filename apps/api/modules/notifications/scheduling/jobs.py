"""
Exact-time jobs (ERD 2.6): firing one when its moment comes. Planning and cancelling are in `planning.py` (re-exported
here, so callers have one place to look).

Reliability rules:
  * `fire_job` claims the row with one conditional UPDATE (`pending` to `fired`). Only the caller that updated one row
    goes on, so a queue retry racing the sweep cannot send twice (FR-N17).
  * After the claim, a failure that may pass puts the job back to `pending` (up to `MAX_ATTEMPTS`) and answers with a
    retryable error; a skip is recorded with its reason and answered normally so the queue does not retry it.
  * A deferred send (`deliver_deferred`) asks `dispatch` again when it fires, so preferences, quiet hours, the cap and the
    expiry are judged at the moment of sending and not at the moment of holding (FR-N33).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from django.db.models import F
from django.utils import timezone

from .. import dispatch as dispatch_module
from .. import flags, handlers
from ..domain.enums import JobKind, JobStatus, SkipReason, SuppressReason
from ..domain.policy import Action
from ..errors import TransientJobError
from ..logs import log_event
from ..models import ScheduledJob
from ..services import notify as notify_service
from .planning import (  # noqa: F401 - the planning surface, re-exported
    cancel_for_stopwatch,
    cancel_for_timer,
    plan_deferred,
    plan_stopwatch_long,
    plan_timer_end,
)

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 3


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


_SUPPRESSION_FOR_SKIP = {SkipReason.DISABLED: SuppressReason.FLAG_OFF, SkipReason.FLAG_OFF: SuppressReason.FLAG_OFF}


def _skip(job: ScheduledJob, reason: SkipReason, now: datetime) -> FireResult:
    ScheduledJob.objects.filter(pk=job.pk).update(
        status=JobStatus.SKIPPED, skip_reason=reason, updated_at=timezone.now()
    )
    if job.kind == JobKind.DELIVER_DEFERRED and reason in _SUPPRESSION_FOR_SKIP:
        # The held push will never be sent: say so on its delivery row instead of leaving it `queued` for ever.
        dispatch_module.close_held(
            job.subject_key, _SUPPRESSION_FOR_SKIP[reason], event=job.context.get("event", ""), now=now
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

    if isinstance(verdict, handlers.Redeliver):
        # A notification that already exists (held by quiet hours, or due now): ask dispatch again with today's facts.
        result = notify_service.deliver(verdict.notification, now=now, intended_at=job.fire_at)
    else:
        result = notify_service.notify(
            job.user_id,
            verdict.event_key,
            context=verdict.context,
            dedupe_ref=verdict.dedupe_parts,
            now=now,
            intended_at=job.fire_at,
        ).dispatch
    if result.action is Action.SUPPRESS and result.reason is SuppressReason.STALE:
        ScheduledJob.objects.filter(pk=job.pk).update(
            status=JobStatus.SKIPPED, skip_reason=SkipReason.STALE, updated_at=timezone.now()
        )
        log_event(logging.INFO, "job_skipped", kind=job.kind, reason="stale", overdue_ms=_overdue_ms(job, now))
        return FireResult(FireOutcome.SKIPPED, reason=SkipReason.STALE.value, delivery=result.outcome)
    log_event(logging.INFO, "job_fired", kind=job.kind, event=event_key, overdue_ms=_overdue_ms(job, now))
    return FireResult(FireOutcome.NOTIFIED, delivery=result.outcome)
