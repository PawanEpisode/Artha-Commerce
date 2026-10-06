"""
What each kind of job means when it fires. A handler answers two questions without side effects: which event would be
sent (so the kill switches can be checked first), and whether the moment is still real (the judgement). `scheduling.jobs`
owns the claim, the recording and the sending; adding a job kind (a long stopwatch, a deferred send) is one handler here
and one registration in `apps.py`.

The timer handler reads `focus` only through its public selector, which is read-only (FR-N18).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol

from modules.focus import selectors as focus_selectors
from modules.focus.domain.judgement import EndState

from .domain.enums import JobKind, SkipReason
from .models import ScheduledJob


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


Verdict = Skip | NotYet | Notify


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


def register_defaults() -> None:
    register(JobKind.TIMER_END, TimerEndHandler())
