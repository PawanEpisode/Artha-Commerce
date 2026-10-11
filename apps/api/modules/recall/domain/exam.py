"""
Exam awareness (PRD 4.7, ERD 3.5), pure: the exam horizon, the retention boost, `R_exam`, the quick-revision set, the cram window
and the pacing assistant. Nothing here reads the clock, the database or the settings; the caller passes `now`, the exam instant
and the numbers. `apps/web/src/modules/recall/lib/exam.ts` is the twin and both must reproduce `vectors/exam_cases.json`.

Decisions (the PRD leaves these open):
- The horizon moves a card only while the exam is more than 1 and at most 90 days away; in the last day the cram preview takes over.
- The slot inside the final window comes from the first 8 hex digits of the card id (not `hash()`, which differs between runs).
- A card is never moved later than the scheduler's own due date, and never earlier than `now + 1 day`.
"""

from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass, replace
from datetime import datetime, timedelta

from .fsrs6 import Cfg, retrievability
from .limits import (
    CRAM_HOURS,
    EXAM_BOOST_DAYS,
    EXAM_BOOST_RETENTION,
    EXAM_HORIZON_DAYS,
    EXAM_LAST_REVIEW_DAYS,
    EXAM_WINDOW_END_DAYS,
    EXAM_WINDOW_SLOTS,
    EXAM_WINDOW_START_DAYS,
    IMPORTANCE_WEIGHTS,
    PACING_LEAD_DAYS,
    PHASE_NEW,
    QUICK_MIN_CARDS,
    QUICK_MIN_IMPORTANCE,
    QUICK_R_TARGET,
    SECONDS_PER_DAY,
)

MANDATORY = 2


def days_between(later: datetime, earlier: datetime) -> float:
    return (later - earlier).total_seconds() / SECONDS_PER_DAY


def days_to_exam(now: datetime, exam_at: datetime | None) -> float | None:
    """Fractional days from `now` to the exam; negative once it has passed; None without an exam date."""
    return None if exam_at is None else days_between(exam_at, now)


def slot_of(card_id: object) -> int:
    """0 to 4: which day of the final window this card is spread to (stable across runs and across languages)."""
    return int(str(card_id).replace("-", "")[:8], 16) % EXAM_WINDOW_SLOTS


def horizon(
    due_at: datetime | None,
    last_review_at: datetime | None,
    exam_at: datetime | None,
    card_id: object,
    now: datetime,
    *,
    enabled: bool = True,
) -> datetime | None:
    """
    The effective due date with the exam horizon applied. A card whose due date falls after `exam - 2d` and that was last
    reviewed at or before `exam - 6d` is moved to `exam - 7d + slot` days (slot 0 to 4), no earlier than `now + 1d` and never
    later than its own due date. Everything else, and everything outside the horizon, keeps its due date.
    """
    if not enabled or due_at is None or exam_at is None:
        return due_at
    left = days_between(exam_at, now)
    if not (CRAM_HOURS / 24 < left <= EXAM_HORIZON_DAYS):
        return due_at
    if due_at <= exam_at - timedelta(days=EXAM_WINDOW_END_DAYS):
        return due_at
    if last_review_at is not None and last_review_at > exam_at - timedelta(days=EXAM_LAST_REVIEW_DAYS):
        return due_at
    window = exam_at - timedelta(days=EXAM_WINDOW_START_DAYS) + timedelta(days=slot_of(card_id))
    return min(due_at, max(window, now + timedelta(days=1)))


def retention_for(importance: int, desired: float, left_days: float | None, *, enabled: bool = True) -> float:
    """Mandatory cards use at least 0.95 in the last 30 days before the exam; everything else the student's own setting."""
    if enabled and importance == MANDATORY and left_days is not None and 0 < left_days <= EXAM_BOOST_DAYS:
        return max(desired, EXAM_BOOST_RETENTION)
    return desired


def cfg_at(cfg: Cfg, importance: int, at: datetime, exam_at: datetime | None, *, enabled: bool = True) -> Cfg:
    """The scheduler configuration for a review of a card of this importance at `at`: the boost, or the student's own `cfg`."""
    wanted = retention_for(importance, cfg.desired_retention, days_to_exam(at, exam_at), enabled=enabled)
    return cfg if wanted == cfg.desired_retention else replace(cfg, desired_retention=wanted)


def r_exam(stability: float | None, last_review_at: datetime | None, exam_at: datetime, w20: float) -> float | None:
    """Predicted recall on exam day if the card is not seen again; None for a card with no memory yet."""
    if stability is None or last_review_at is None:
        return None
    return retrievability(stability, days_between(exam_at, last_review_at), w20)


# ---------------------------------------------------------------- quick revision


@dataclass(frozen=True)
class QuickCard:
    id: str
    importance: int
    phase: int
    stability: float | None
    last_review_at: datetime | None
    boosted: bool = (
        False  # a mandatory card of a chapter due for revision (FR-F15-63): taken before the rest when the budget cuts
    )


@dataclass(frozen=True)
class QuickPlan:
    ids: tuple[str, ...]  # the cards to study, most at risk first
    candidates: int  # how many cards qualified
    selected: int
    cut_off: int  # qualified but left out by the minute budget
    days_to_exam: int  # whole days left
    window_days: int  # days available: all but the last two
    per_day: int  # cards a day to see every selected card once before the last two days
    minutes_per_day: int  # what that costs a day at the student's pace
    too_few: bool  # fewer than 20 candidates: no plan worth making


def quick_set(
    cards: Iterable[QuickCard],
    exam_at: datetime,
    minutes_per_day: int,
    median_seconds: float,
    now: datetime,
    w20: float,
) -> QuickPlan:
    """
    Mandatory and important cards likely forgotten by exam day (`R_exam` below 0.90) plus unseen mandatory cards, ordered by
    `importance weight x (1 - R_exam)` and cut to what `minutes_per_day` allows over the days that remain before `exam - 2d`.
    """
    left = days_between(exam_at, now)
    window = max(math.floor(left) - EXAM_WINDOW_END_DAYS, 0)
    scored: list[tuple[float, str]] = []
    urgent: set[str] = set()
    for c in cards:
        if c.importance < QUICK_MIN_IMPORTANCE:
            continue
        weight = IMPORTANCE_WEIGHTS[min(max(c.importance, 0), len(IMPORTANCE_WEIGHTS) - 1)]
        if c.phase == PHASE_NEW:
            if c.importance == MANDATORY:
                scored.append((weight, c.id))
                if c.boosted:
                    urgent.add(c.id)
            continue
        r = r_exam(c.stability, c.last_review_at, exam_at, w20)
        if r is not None and r < QUICK_R_TARGET:
            scored.append((weight * (1.0 - r), c.id))
            if c.boosted:
                urgent.add(c.id)
    scored.sort(key=lambda t: (t[1] not in urgent, -t[0], t[1]))
    seconds = max(median_seconds, 1.0)
    size = math.floor(minutes_per_day * window * 60 / seconds) if window else 0
    chosen = tuple(i for _, i in scored[:size])
    per_day = math.ceil(len(chosen) / window) if window else 0
    minutes = math.ceil(len(chosen) * seconds / 60 / window) if window else 0
    return QuickPlan(
        chosen,
        len(scored),
        len(chosen),
        len(scored) - len(chosen),
        max(math.floor(left), 0),
        window,
        per_day,
        minutes,
        len(scored) < QUICK_MIN_CARDS,
    )


# ---------------------------------------------------------------- cram, pacing


def cram_open(now: datetime, exam_at: datetime | None) -> bool:
    """The cram preview (read-through, no scheduling) is available in the last 24 hours before the exam."""
    left = days_to_exam(now, exam_at)
    return left is not None and 0 < left <= CRAM_HOURS / 24


@dataclass(frozen=True)
class Pacing:
    unseen: int  # cards in scope not yet introduced
    window_days: int  # days left to introduce them: until `exam - 14d`
    new_per_day: int  # the student's limit
    introduced_at_limit: int  # how many that limit introduces in the window
    needed_per_day: int  # what it takes to introduce them all
    feasible: bool


def pacing(unseen_in_scope: int, days_left: float, new_per_day: int) -> Pacing:
    """The new-cards-per-day needed to introduce everything in scope by `exam - 14d`, and whether the limit gets there."""
    window = max(math.floor(days_left) - PACING_LEAD_DAYS, 0)
    unseen = max(unseen_in_scope, 0)
    at_limit = min(unseen, new_per_day * window)
    needed = 0 if unseen == 0 else (math.ceil(unseen / window) if window else unseen)
    return Pacing(unseen, window, new_per_day, at_limit, needed, at_limit >= unseen)
