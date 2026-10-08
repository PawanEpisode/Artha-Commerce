"""
Replay (ERD 3.5, "Replay"): a card's memory state is a pure function of its facts, so it can be rebuilt at any time.
`fold` takes a card's reviews and schedule events in any order, with duplicates, and returns the state the incremental
path must also reach. A property test applies random orders, duplicates and voids and compares the result.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime

from .fsrs6 import Cfg, MemoryState, cap_stability, review
from .limits import CONTENT_RESET_STABILITY_CAP_DAYS, PHASE_NEW


@dataclass(frozen=True)
class ReviewEvent:
    id: str
    at: datetime  # reviewed_at
    rating: int
    counts_for_scheduling: bool = True
    voided: bool = False


@dataclass(frozen=True)
class ScheduleEvent:
    """`forget`, `content_reset`, `postpone`, `unpostpone` change state; every other kind is audit only and is ignored."""

    id: str
    at: datetime
    kind: str
    to_due: datetime | None = None
    cap_days: float | None = None


@dataclass(frozen=True)
class CardState:
    memory: MemoryState
    due_scheduled_at: datetime | None  # raw scheduler due; None while new
    postponed_until: datetime | None  # rebalance or snooze, cleared by the next review


def new_card_state() -> CardState:
    return CardState(MemoryState(), None, None)


def effective_due(state: CardState) -> datetime | None:
    """The later of the scheduler's due and a postponement (the exam horizon of R2 is applied on top by the caller)."""
    if state.due_scheduled_at is None:
        return None
    if state.postponed_until is None:
        return state.due_scheduled_at
    return max(state.due_scheduled_at, state.postponed_until)


def _order(event: ReviewEvent | ScheduleEvent) -> tuple[datetime, int, str]:
    # At the same instant a schedule event (a reset, a postponement) applies before the review
    return (event.at, 0 if isinstance(event, ScheduleEvent) else 1, event.id)


def apply_event(
    state: CardState, event: ReviewEvent | ScheduleEvent, w: Sequence[float], cfg: Cfg, *, card_id: object
) -> CardState:
    """One step of the fold. The incremental fast path of the review service is this function applied in time order."""
    if isinstance(event, ReviewEvent):
        if not event.counts_for_scheduling or event.voided:
            return state
        out = review(state.memory, event.rating, event.at, w, cfg, card_id=card_id)
        return CardState(out.state, out.due_at, None)
    if event.kind == "forget":
        return new_card_state()
    if event.kind == "content_reset":
        memory = cap_stability(state.memory, event.cap_days or CONTENT_RESET_STABILITY_CAP_DAYS)
        if memory.phase == PHASE_NEW:
            return CardState(memory, state.due_scheduled_at, state.postponed_until)
        return CardState(memory, event.at, None)
    if event.kind == "postpone":
        return CardState(state.memory, state.due_scheduled_at, event.to_due)
    if event.kind == "unpostpone":
        return CardState(state.memory, state.due_scheduled_at, None)
    return state


def fold(events: Iterable[ReviewEvent | ScheduleEvent], w: Sequence[float], cfg: Cfg, *, card_id: object) -> CardState:
    """Rebuild a card from its facts. Order of the input does not matter; an event id seen twice counts once."""
    seen: set[tuple[str, str]] = set()
    state = new_card_state()
    for event in sorted(events, key=_order):
        key = ("s" if isinstance(event, ScheduleEvent) else "r", event.id)
        if key in seen:
            continue
        seen.add(key)
        state = apply_event(state, event, w, cfg, card_id=card_id)
    return state
