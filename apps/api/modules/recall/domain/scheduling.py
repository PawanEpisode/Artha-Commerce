"""
Queue, catch-up, forgotten list, streak and forecast (ERD 3.5 and 4). Pure functions of the data passed in: nothing here
reads the clock, the database or the settings; the caller supplies `now`, the card views and the student's numbers.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from .fsrs6 import retrievability
from .limits import (
    CATCHUP_DUE_FACTOR,
    CATCHUP_OVERDUE_DAYS,
    FORGOTTEN_MIN_SCORE,
    IMPORTANCE_WEIGHTS,
    MAX_DAYS_TO_CLEAR,
    NEW_AFTER_REVIEWS,
    OVERDUE_PRIORITY_CAP_DAYS,
    OVERDUE_PRIORITY_PER_DAY,
    PHASE_LEARNING,
    PHASE_NEW,
    PHASE_RELEARNING,
    REVIEW_AHEAD_BATCH,
    SECONDS_PER_DAY,
    STREAK_MIN_REVIEWS,
    SUBJECT_WINDOW,
)


@dataclass(frozen=True)
class CardView:
    """What the queue needs to know about one card. `due_at` is the effective due (None for a new card)."""

    id: str
    subject: str
    importance: int  # 0 bullet, 1 important, 2 mandatory
    phase: int
    stability: float | None
    last_review_at: datetime | None
    due_at: datetime | None
    created_at: datetime | None = None


@dataclass(frozen=True)
class Limits:
    new_per_day: int
    reviews_per_day: int
    new_done_today: int = 0
    reviews_done_today: int = 0


@dataclass(frozen=True)
class Catchup:
    active: bool
    due_count: int
    oldest_overdue_days: float
    days_to_clear: int


@dataclass(frozen=True)
class Queue:
    ids: tuple[str, ...]  # the order to study in
    learning: int
    reviews: int
    new: int
    catchup: Catchup


# ---------------------------------------------------------------- study day


def local_date_of(instant: datetime, tz: str, day_start_hour: int) -> date:
    """The study day an instant belongs to: the local date after shifting back by the day-start hour."""
    return (instant.astimezone(ZoneInfo(tz)) - timedelta(hours=day_start_hour)).date()


def study_day_start(day: date, tz: str, day_start_hour: int) -> datetime:
    """The instant (aware, in the student's zone) at which a study day begins."""
    zone = ZoneInfo(tz)
    return datetime(day.year, day.month, day.day, day_start_hour, tzinfo=zone)


def end_of_study_day(instant: datetime, tz: str, day_start_hour: int) -> datetime:
    """The first instant of the next study day; reviews due before it count as "due today"."""
    return study_day_start(local_date_of(instant, tz, day_start_hour) + timedelta(days=1), tz, day_start_hour)


# ---------------------------------------------------------------- priority


def _r_now(card: CardView, now: datetime, w20: float) -> float:
    if card.stability is None or card.last_review_at is None:
        return 1.0
    elapsed = max(0.0, (now - card.last_review_at).total_seconds() / SECONDS_PER_DAY)
    return retrievability(card.stability, elapsed, w20)


def overdue_days(card: CardView, now: datetime) -> float:
    if card.due_at is None:
        return 0.0
    return max(0.0, (now - card.due_at).total_seconds() / SECONDS_PER_DAY)


def priority(importance: int, r: float, overdue: float) -> float:
    """`weight * (1 - R) + 0.02 * min(overdue days, 30)`: what is most at risk and most important comes first."""
    weight = IMPORTANCE_WEIGHTS[min(max(importance, 0), len(IMPORTANCE_WEIGHTS) - 1)]
    return weight * (1.0 - r) + OVERDUE_PRIORITY_PER_DAY * min(overdue, OVERDUE_PRIORITY_CAP_DAYS)


# ---------------------------------------------------------------- catch-up


def days_to_clear(due_count: int, reviews_per_day: int) -> int:
    if due_count <= 0:
        return 0
    return min(math.ceil(due_count / max(reviews_per_day, 1)), MAX_DAYS_TO_CLEAR)


def catchup_state(due_count: int, oldest_overdue_days: float, reviews_per_day: int, mode: str = "auto") -> Catchup:
    """Catch-up mode: `on` and `off` are the student's override; `auto` follows the ERD rule."""
    clear = days_to_clear(due_count, reviews_per_day)
    if mode == "on":
        active = due_count > 0
    elif mode == "off":
        active = False
    else:
        active = due_count > CATCHUP_DUE_FACTOR * reviews_per_day or (
            oldest_overdue_days > CATCHUP_OVERDUE_DAYS and clear > 1
        )
    return Catchup(active, due_count, oldest_overdue_days, clear)


# ---------------------------------------------------------------- queue


def _alternate_subjects(cards: Sequence[CardView]) -> list[CardView]:
    """Spread subjects: when the next card has the subject just shown, take the first different one within the window."""
    pending = list(cards)
    out: list[CardView] = []
    while pending:
        pick = 0
        if out and pending[0].subject == out[-1].subject:
            for i in range(1, min(len(pending), SUBJECT_WINDOW)):
                if pending[i].subject != out[-1].subject:
                    pick = i
                    break
        out.append(pending.pop(pick))
    return out


def plan_queue(
    cards: Iterable[CardView],
    now: datetime,
    limits: Limits,
    w20: float,
    *,
    mode: str = "auto",
    day_end: datetime | None = None,
) -> Queue:
    """
    Today's order: learning cards due now (by due time), then reviews by priority with subjects alternated, with one new
    card after every three reviews. New cards are cut at the daily new limit; reviews at the reviews limit. Catch-up
    mode drops new cards, because a backlog is cleared before more is added. `day_end` bounds "due today".
    """
    learning: list[CardView] = []
    reviews: list[tuple[float, CardView]] = []
    fresh: list[CardView] = []
    for card in cards:
        if card.phase == PHASE_NEW or card.due_at is None:
            fresh.append(card)
        elif card.phase in (PHASE_LEARNING, PHASE_RELEARNING):
            if card.due_at <= now:
                learning.append(card)
        elif card.due_at <= (day_end or now):
            reviews.append((priority(card.importance, _r_now(card, now, w20), overdue_days(card, now)), card))

    due_reviews = [c for _, c in reviews]
    oldest = max((overdue_days(c, now) for c in due_reviews), default=0.0)
    catchup = catchup_state(len(due_reviews), oldest, limits.reviews_per_day, mode)

    learning.sort(key=lambda c: (c.due_at, c.id))
    reviews.sort(key=lambda t: (-t[0], t[1].due_at, t[1].id))
    room = max(limits.reviews_per_day - limits.reviews_done_today, 0)
    ordered_reviews = _alternate_subjects([c for _, c in reviews][:room])

    fresh.sort(key=lambda c: (-c.importance, c.created_at or now, c.id))
    new_room = 0 if catchup.active else max(limits.new_per_day - limits.new_done_today, 0)
    new_cards = fresh[:new_room]

    merged: list[str] = [c.id for c in learning]
    queue_new = iter(new_cards)
    since_new = 0
    for card in ordered_reviews:
        merged.append(card.id)
        since_new += 1
        if since_new == NEW_AFTER_REVIEWS:
            nxt = next(queue_new, None)
            if nxt is not None:
                merged.append(nxt.id)
            since_new = 0
    merged.extend(c.id for c in queue_new)
    return Queue(tuple(merged), len(learning), len(ordered_reviews), len(new_cards), catchup)


def review_ahead(
    cards: Iterable[CardView], now: datetime, w20: float, *, size: int = REVIEW_AHEAD_BATCH
) -> tuple[str, ...]:
    """Extra practice after the queue is cleared: reviewed cards not yet due, lowest retrievability first."""
    candidates = [
        (_r_now(c, now, w20), c.id)
        for c in cards
        if c.phase not in (PHASE_NEW, PHASE_LEARNING, PHASE_RELEARNING) and c.due_at is not None and c.due_at > now
    ]
    candidates.sort()
    return tuple(i for _, i in candidates[:size])


# ---------------------------------------------------------------- forgotten list, streak, forecast


def forgetting_score(lapses_in_window: int, agains_in_window: int) -> float:
    """Two points per lapse in the last 30 days, one per Again in the last 14 (the caller counts the windows)."""
    return 2.0 * lapses_in_window + 1.0 * agains_in_window


def is_forgotten(lapses_in_window: int, agains_in_window: int) -> bool:
    return forgetting_score(lapses_in_window, agains_in_window) >= FORGOTTEN_MIN_SCORE


def streak(reviews_by_day: Mapping[date, int], today: date, *, min_reviews: int = STREAK_MIN_REVIEWS) -> int:
    """
    Consecutive study days with at least `min_reviews` reviews, ending today; if today has not yet reached the minimum
    the run ending yesterday still counts, so the streak is not lost before the day is over.
    """
    day = today if reviews_by_day.get(today, 0) >= min_reviews else today - timedelta(days=1)
    count = 0
    while reviews_by_day.get(day, 0) >= min_reviews:
        count += 1
        day -= timedelta(days=1)
    return count


def forecast(due_dates: Iterable[date | None], today: date, days: int = 14) -> list[int]:
    """Reviews due on each of the next `days` study days; overdue cards count on day 0, further dates are ignored."""
    out = [0] * days
    for due in due_dates:
        if due is None:
            continue
        offset = max((due - today).days, 0)
        if offset < days:
            out[offset] += 1
    return out


# ---------------------------------------------------------------- R2 (exam horizon): not part of R1


def horizon(*_args: object, **_kwargs: object) -> None:
    raise NotImplementedError("Exam horizon arrives in R2.")


def r_exam(*_args: object, **_kwargs: object) -> None:
    raise NotImplementedError("Exam retrievability arrives in R2.")


def quick_set(*_args: object, **_kwargs: object) -> None:
    raise NotImplementedError("Quick sets arrive in R2.")


def pacing(*_args: object, **_kwargs: object) -> None:
    raise NotImplementedError("Pacing arrives in R2.")
