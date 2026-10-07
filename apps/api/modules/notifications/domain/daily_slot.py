"""
What the student's one daily push says (X-01.1 W3.4). The daily nudge time is a single slot: at that moment a student
gets at most one push from the "daily" family, and this module picks which. Pure: facts in, a pick out.

Order of importance:
  1. an exam milestone, on the exact day the exam is 60, 30, 14, 7, 3 or 1 days away (FR-N29 amendment: more than the
     three the first draft listed, chosen by the product owner);
  2. revision, when at least one chapter is due today;
  3. the daily thought (W3.3), which is what the slot carries when there is nothing more useful to say.

A category the student turned off for push is skipped, so the next one goes out and they still hear from us. A
milestone that loses to nothing is never "owed": it is tied to the exact day, so a student who misses the day (the sweep
was down, a visit cancelled a push) simply does not get it. Revision is different: still due tomorrow, so it is offered
again on the next day by the same rule, which is why a displaced revision push is not lost.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

MILESTONES: tuple[int, ...] = (60, 30, 14, 7, 3, 1)


class Slot(StrEnum):
    EXAM = "exam"
    REVISION = "revision"
    THOUGHT = "thought"


@dataclass(frozen=True)
class Pick:
    slot: Slot
    days_left: int | None = None  # set for an exam milestone


def milestone_for(days_left: int | None) -> int | None:
    """`days_left` when it is exactly a milestone day, else None."""
    return days_left if days_left in MILESTONES else None


def choose(*, days_left: int | None, due_count: int, exam_on: bool, revision_on: bool) -> Pick:
    """
    `days_left`: whole days from the student's local today to their exam, or None without an exam date.
    `due_count`: chapters due for revision today.
    `exam_on` and `revision_on`: whether that category may reach the student at all (their push choice, the kill
    switch for the event). The caller decides these; this function only orders the possibilities.
    """
    milestone = milestone_for(days_left)
    if exam_on and milestone is not None:
        return Pick(Slot.EXAM, days_left=milestone)
    if revision_on and due_count > 0:
        return Pick(Slot.REVISION)
    return Pick(Slot.THOUGHT)
