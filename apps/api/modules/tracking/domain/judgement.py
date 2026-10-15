"""
Pure answer to "is the long-stopwatch alert for this stopwatch still the right thing to say?" (X-01.1 FR-N18 applied to
the stopwatch). It works from the columns of the live stopwatch row and the clock only. It never settles anything: an
unanswered "Still studying?" prompt pauses the stopwatch lazily when a request reads it, so the judge applies the same
rule to the row without writing, and asking never changes the stopwatch.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum

from . import durations

# The queue runs on its own clock; an alert that arrives a moment before this server's clock reaches the mark is fine.
EARLY_TOLERANCE = timedelta(seconds=5)


class RunState(StrEnum):
    DUE = "due"  # running, and the counted time has reached the mark
    GONE = "gone"  # no stopwatch any more (stopped, discarded, account erased)
    CHANGED = "changed"  # another stopwatch or another version: paused, resumed, retagged
    PAUSED = "paused"  # same version but paused, or an unanswered idle prompt has already paused it
    NOT_DUE = "not_due"  # called before the mark; try again later


@dataclass(frozen=True)
class StopwatchFacts:
    """The columns of the live stopwatch the judgement needs."""

    client_id: object
    version: int
    started_at: datetime
    paused_at: datetime | None
    paused_total_seconds: int
    idle_pending: bool
    idle_prompted_at: datetime | None


@dataclass(frozen=True)
class RunJudgement:
    state: RunState
    elapsed_seconds: int = 0  # counted time at `now`; meaningful for DUE and NOT_DUE


def reaches_at(started_at: datetime, paused_total_seconds: int, after_seconds: int) -> datetime:
    """
    The instant a stopwatch that keeps running reaches `after_seconds` of counted time: its start, plus the pauses it has
    already had, plus the mark. Valid for a running stopwatch (a pause moves it, and a resume plans it again).
    """
    return started_at + timedelta(seconds=paused_total_seconds + after_seconds)


def judge_running(
    facts: StopwatchFacts | None, *, client_id, expected_version: int, now: datetime, after_seconds: int
) -> RunJudgement:
    if facts is None:
        return RunJudgement(RunState.GONE)
    if str(facts.client_id) != str(client_id) or facts.version != expected_version:
        return RunJudgement(RunState.CHANGED)
    if facts.paused_at is not None:
        return RunJudgement(RunState.PAUSED)
    if facts.idle_pending and durations.idle_expired(now, facts.idle_prompted_at):
        return RunJudgement(RunState.PAUSED)
    elapsed = durations.elapsed_seconds(facts.started_at, now, None, facts.paused_total_seconds)
    if timedelta(seconds=elapsed) < timedelta(seconds=after_seconds) - EARLY_TOLERANCE:
        return RunJudgement(RunState.NOT_DUE, elapsed_seconds=elapsed)
    return RunJudgement(RunState.DUE, elapsed_seconds=elapsed)


class IdleState(StrEnum):
    DUE = "due"
    GONE = "gone"
    CHANGED = "changed"
    PAUSED = "paused"
    ALREADY_PENDING = "already_pending"
    RESCHEDULE = "reschedule"
    PAGE_ALIVE = "page_alive"


@dataclass(frozen=True)
class StopwatchIdleFacts:
    client_id: object
    version: int
    started_at: datetime
    paused_at: datetime | None
    last_seen_at: datetime
    last_active_at: datetime
    idle_pending: bool
    idle_prompted_at: datetime | None
    idle_minutes: int
    subject_name: str | None = None


@dataclass(frozen=True)
class IdleJudgement:
    state: IdleState
    reschedule_at: datetime | None = None
    subject_name: str | None = None
    spell: int | None = None


def judge_idle(facts: StopwatchIdleFacts | None, *, client_id, expected_version: int, now: datetime) -> IdleJudgement:
    if facts is None:
        return IdleJudgement(IdleState.GONE)
    if str(facts.client_id) != str(client_id) or facts.version != expected_version:
        return IdleJudgement(IdleState.CHANGED)
    if facts.paused_at is not None:
        return IdleJudgement(IdleState.PAUSED)
    if facts.idle_pending and durations.idle_expired(now, facts.idle_prompted_at):
        return IdleJudgement(IdleState.PAUSED)
    if facts.idle_pending:
        return IdleJudgement(IdleState.ALREADY_PENDING)
    if facts.idle_minutes <= 0:
        return IdleJudgement(IdleState.CHANGED)

    new_due_at = facts.last_active_at + timedelta(minutes=facts.idle_minutes)
    if new_due_at > now + EARLY_TOLERANCE:
        return IdleJudgement(IdleState.RESCHEDULE, reschedule_at=new_due_at)

    if now - facts.last_seen_at < timedelta(seconds=90):
        return IdleJudgement(IdleState.PAGE_ALIVE)

    return IdleJudgement(
        IdleState.DUE,
        subject_name=facts.subject_name,
        spell=int(facts.last_active_at.timestamp()),
    )
