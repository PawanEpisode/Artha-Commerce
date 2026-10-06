"""
What each kind of job means when it fires. A handler answers two questions without side effects: which event would be
sent (so the kill switches can be checked first), and whether the moment is still real (the judgement). `scheduling.jobs`
owns the claim, the recording and the sending; adding a job kind (a long stopwatch, a deferred send) is one handler here
and one registration in `apps.py`.

The timer handler reads `focus`, and the stopwatch handler `tracking`, only through their public read-only selectors
(FR-N18). The deferred handler reads only its own notification.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol

from django.core.exceptions import ValidationError

from modules.focus import selectors as focus_selectors
from modules.focus.domain.judgement import EndState
from modules.tracking import selectors as tracking_selectors
from modules.tracking.domain.judgement import RunState

from .domain import tracker_alerts
from .domain.enums import JobKind, SkipReason
from .models import Notification, ScheduledJob


@dataclass(frozen=True)
class Skip:
    """Send nothing; the job is recorded as skipped for this reason."""

    reason: SkipReason


@dataclass(frozen=True)
class NotYet:
    """Called too early. The job goes back to pending and the call is answered with a retryable error."""


@dataclass(frozen=True)
class Notify:
    """Create this notification (idempotent on the dedupe parts) and send it."""

    event_key: str
    context: dict[str, Any]
    dedupe_parts: dict[str, object]


@dataclass(frozen=True)
class Redeliver:
    """Send this existing notification again through dispatch (held by quiet hours, or due now), judged afresh."""

    notification: Notification


Verdict = Skip | NotYet | Notify | Redeliver


class JobHandler(Protocol):
    def event_key(self, job: ScheduledJob) -> str: ...

    def judge(self, job: ScheduledJob, now: datetime) -> Verdict: ...


class UnknownJobKind(KeyError):
    pass


_registry: dict[str, JobHandler] = {}


def register(kind: str, handler: JobHandler) -> None:
    _registry[str(kind)] = handler


def get(kind: str) -> JobHandler:
    try:
        return _registry[str(kind)]
    except KeyError:
        raise UnknownJobKind(kind) from None


class TimerEndHandler:
    """`timer_end` jobs: a focus round reached its end (`timer_end`) or a break did (`break_over`)."""

    def event_key(self, job: ScheduledJob) -> str:
        return "timer_end" if job.context.get("phase", "focus") == "focus" else "break_over"

    def judge(self, job: ScheduledJob, now: datetime) -> Verdict:
        judgement = focus_selectors.timer_end_judgement(
            job.user_id, job.subject_key, job.expected_version, now, planned_end=job.fire_at
        )
        match judgement.state:
            case EndState.GONE:
                return Skip(SkipReason.GONE)
            case EndState.CHANGED:
                return Skip(SkipReason.CHANGED)
            case EndState.PAUSED:
                return Skip(SkipReason.PAUSED)
            case EndState.NOT_DUE:
                return NotYet()
        # Ended. Whether the round is still running (overtime) or closed is a live fact, so it comes from the judge.
        context = {**job.context, "client_id": job.subject_key, "overtime": judgement.overtime}
        return Notify(self.event_key(job), context, {"client_id": job.subject_key, "version": job.expected_version})


class StopwatchLongHandler:
    """`stopwatch_long` jobs: a stopwatch has been counting for a long time and may have been forgotten."""

    def event_key(self, job: ScheduledJob) -> str:
        return "stopwatch_long"

    def judge(self, job: ScheduledJob, now: datetime) -> Verdict:
        judgement = tracking_selectors.stopwatch_running_judgement(
            job.user_id,
            job.subject_key,
            job.expected_version,
            now,
            after_seconds=tracker_alerts.stopwatch_long_after_seconds(),
        )
        match judgement.state:
            case RunState.GONE:
                return Skip(SkipReason.GONE)
            case RunState.CHANGED:
                return Skip(SkipReason.CHANGED)
            case RunState.PAUSED:
                return Skip(SkipReason.PAUSED)
            case RunState.NOT_DUE:
                return NotYet()
        context = {"client_id": job.subject_key, "minutes": judgement.elapsed_seconds // 60}
        return Notify(self.event_key(job), context, {"client_id": job.subject_key})


class DeliverDeferredHandler:
    """
    `deliver_deferred` jobs (FR-N33): a notification that exists and has to be pushed at this moment, either because quiet
    hours held it until now or because it is due at once and must not be sent inside the student's own request.
    """

    def event_key(self, job: ScheduledJob) -> str:
        return str(job.context.get("event", ""))

    def judge(self, job: ScheduledJob, now: datetime) -> Verdict:
        try:
            notification = Notification.objects.filter(pk=job.subject_key, user_id=job.user_id).first()
        except (ValueError, TypeError, ValidationError):  # not a UUID: nothing we planned
            notification = None
        if notification is None:
            return Skip(SkipReason.GONE)
        return Redeliver(notification)


def register_defaults() -> None:
    register(JobKind.TIMER_END, TimerEndHandler())
    register(JobKind.STOPWATCH_LONG, StopwatchLongHandler())
    register(JobKind.DELIVER_DEFERRED, DeliverDeferredHandler())
