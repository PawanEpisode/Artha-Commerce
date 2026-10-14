"""Counters, the "day completed" rule and day summaries for the week strip (PRD FR-F13-31 to 35). Pure."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from .constants import OPEN_STATES, PLANNED_STATES


@dataclass(frozen=True)
class Counters:
    planned_count: int = 0
    done_count: int = 0
    skipped_count: int = 0
    open_count: int = 0
    snoozed_count: int = 0
    planned_minutes: int = 0
    open_minutes: int = 0


def recount(tasks: Iterable[tuple[str, int, bool]]) -> Counters:
    """
    Reference implementation of the plan counters from `(state, est_minutes, counts_toward_day)` rows (ERD 3.5). The services do
    the same in one SQL statement under the plan lock; a property test asserts both agree after random transitions.
    """
    planned = done = skipped = open_ = snoozed = planned_min = open_min = 0
    for state, minutes, counts in tasks:
        if state == "snoozed":
            snoozed += 1
        if not counts:
            continue
        if state in PLANNED_STATES:
            planned += 1
            planned_min += minutes
        if state == "done":
            done += 1
        elif state == "skipped":
            skipped += 1
        if state in OPEN_STATES:
            open_ += 1
            open_min += minutes
    return Counters(planned, done, skipped, open_, snoozed, planned_min, open_min)


def day_completed(*, open_count: int, done_count: int, skipped_count: int) -> bool:
    """Nothing left open, at least one done, and at least half of what was resolved was done."""
    return open_count == 0 and done_count >= 1 and 2 * done_count >= done_count + skipped_count


def day_closing(*, open_count: int, done_count: int, skipped_count: int) -> str | None:
    """
    What the screen says when nothing is left open: `celebrate` (a real day), `calm` ("You did 1 and skipped 5. Tomorrow is a
    fresh start", no confetti) or None while tasks are still open or the plan was empty.
    """
    if open_count > 0 or done_count + skipped_count == 0:
        return None
    if day_completed(open_count=open_count, done_count=done_count, skipped_count=skipped_count):
        return "celebrate"
    return "calm"


def day_outcome(*, planned_count: int, done_count: int, completed: bool) -> str:
    """The week strip dot: `all`, `some`, `none` (a plan with nothing done) or `no_plan`."""
    if planned_count == 0:
        return "no_plan"
    if completed:
        return "all"
    return "some" if done_count > 0 else "none"
