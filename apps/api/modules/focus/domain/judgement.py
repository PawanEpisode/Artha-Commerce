"""
Pure answer to "is this timer-end alert still worth sending?" (PRD FR-N18). It works from the facts of the live timer
row and the clock only. It never settles anything: the timer settles lazily when a student's request reads it, and the
alert for a round end must fire whether or not that has happened yet.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum

from . import timing

# The queue runs on its own clock; an alert that arrives a moment before this server's clock reaches the end is fine.
EARLY_TOLERANCE = timedelta(seconds=5)


class EndState(StrEnum):
    ENDED = "ended"  # the planned end was reached and the alert is still the right thing to say
    GONE = "gone"  # no timer any more (stopped, discarded, finished, account erased)
    CHANGED = "changed"  # another timer or another version: paused, resumed, extended, a new phase
    PAUSED = "paused"  # same version but paused, so no end is coming
    NOT_DUE = "not_due"  # called before the end; try again later


@dataclass(frozen=True)
class TimerFacts:
    """The columns of the live timer the judgement needs."""

    client_id: object
    version: int
    phase: str
    started_at: datetime
    planned_seconds: int
    paused_at: datetime | None
    paused_total_seconds: int
    away_pending: bool
    overtime_enabled: bool


@dataclass(frozen=True)
class TimerEndJudgement:
    state: EndState
    phase: str | None = None
    ends_at: datetime | None = None
    # A focus round that reached its target and keeps running (overtime). False once it is closed or the student is away.
    overtime: bool = False
    away_pending: bool = False


def judge_timer_end(
    facts: TimerFacts | None,
    *,
    client_id,
    expected_version: int,
    now: datetime,
    planned_end: datetime | None = None,
) -> TimerEndJudgement:
    """
    `planned_end` is the instant the job was planned for. It lets the judge recognise one benign version change: when a
    request settled the round after its end while the student was away, the version moved by one and `away_pending` was
    set, but the end did not move. The alert is still owed (the student is away, which is the point of it).
    """
    if facts is None:
        return TimerEndJudgement(EndState.GONE)
    if str(facts.client_id) != str(client_id):
        return TimerEndJudgement(EndState.CHANGED, phase=facts.phase)

    ends_at = timing.phase_end_at(facts.started_at, facts.planned_seconds, facts.paused_total_seconds)
    if facts.version != expected_version:
        settled_while_away = (
            facts.away_pending
            and facts.phase == "focus"
            and facts.version == expected_version + 1
            and planned_end is not None
            and ends_at == planned_end
        )
        if not settled_while_away:
            return TimerEndJudgement(EndState.CHANGED, phase=facts.phase)
    elif facts.paused_at is not None:
        return TimerEndJudgement(EndState.PAUSED, phase=facts.phase)
    elif now < ends_at - EARLY_TOLERANCE:
        return TimerEndJudgement(EndState.NOT_DUE, phase=facts.phase, ends_at=ends_at)

    return TimerEndJudgement(
        EndState.ENDED,
        phase=facts.phase,
        ends_at=ends_at,
        overtime=facts.phase == "focus" and facts.overtime_enabled and not facts.away_pending,
        away_pending=facts.away_pending,
    )
