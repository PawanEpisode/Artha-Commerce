"""Reads for the daily slot (X-01.1 W3.4): how far the exam is, what is due for revision, and what the student allows."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from modules.coverage import selectors as coverage_selectors

from ..domain.catalogue import get_event, is_enabled
from ..domain.enums import Channel
from . import preferences as preference_selectors


@dataclass(frozen=True)
class DailyFacts:
    days_left: int | None  # whole days from the student's local today to the exam, None without an exam date
    due_count: int  # chapters due for revision today
    first_chapter: str | None  # the one to start with (overdue first, then the heaviest)


def daily_facts(user_id, local_date: date) -> DailyFacts:
    """Read through `coverage`'s public selectors; a student with no active enrolment has nothing to count down or revise."""
    enrollment = coverage_selectors.get_active_enrollment(user_id)
    if enrollment is None:
        return DailyFacts(None, 0, None)
    days_left = (enrollment.exam_date - local_date).days if enrollment.exam_date else None
    due = coverage_selectors.due_for_revision(enrollment, local_date)
    return DailyFacts(days_left, len(due), due[0].chapter.name if due else None)


def push_allowed(user_id, events: tuple[str, ...]) -> dict[str, bool]:
    """For each event, whether the student's choice lets its category reach them by push (switches are checked apart)."""
    chosen = preference_selectors.overrides(user_id)
    return {event: is_enabled(get_event(event).category.value, Channel.PUSH.value, chosen) for event in events}
