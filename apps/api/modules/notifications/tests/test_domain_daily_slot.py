"""Which push the student's daily slot carries (X-01.1 W3.4). Pure: no database, no clock."""

import pytest

from modules.notifications.domain import daily_slot
from modules.notifications.domain.daily_slot import Pick, Slot


@pytest.mark.parametrize("days_left", [60, 30, 14, 7, 3, 1])
def test_each_milestone_day_is_a_milestone(days_left):
    assert daily_slot.milestone_for(days_left) == days_left


@pytest.mark.parametrize("days_left", [None, -3, 0, 2, 5, 29, 31, 59, 61, 200])
def test_every_other_day_is_not(days_left):
    assert daily_slot.milestone_for(days_left) is None


def test_the_milestones_are_in_descending_order_and_unique():
    assert list(daily_slot.MILESTONES) == sorted(set(daily_slot.MILESTONES), reverse=True)


def test_a_milestone_day_wins_over_revision_and_the_thought():
    pick = daily_slot.choose(days_left=30, due_count=4, exam_on=True, revision_on=True)
    assert pick == Pick(Slot.EXAM, days_left=30)


def test_revision_replaces_the_thought_when_chapters_are_due():
    assert daily_slot.choose(days_left=45, due_count=2, exam_on=True, revision_on=True) == Pick(Slot.REVISION)


def test_the_thought_is_the_default():
    assert daily_slot.choose(days_left=45, due_count=0, exam_on=True, revision_on=True) == Pick(Slot.THOUGHT)
    assert daily_slot.choose(days_left=None, due_count=0, exam_on=True, revision_on=True) == Pick(Slot.THOUGHT)


def test_a_student_with_no_exam_date_can_still_get_revision():
    assert daily_slot.choose(days_left=None, due_count=1, exam_on=True, revision_on=True) == Pick(Slot.REVISION)


def test_a_category_the_student_turned_off_is_skipped_so_the_next_one_goes_out():
    off_exam = daily_slot.choose(days_left=7, due_count=3, exam_on=False, revision_on=True)
    assert off_exam == Pick(Slot.REVISION)
    off_both = daily_slot.choose(days_left=7, due_count=3, exam_on=False, revision_on=False)
    assert off_both == Pick(Slot.THOUGHT)
    off_revision = daily_slot.choose(days_left=45, due_count=3, exam_on=True, revision_on=False)
    assert off_revision == Pick(Slot.THOUGHT)


def test_a_milestone_that_was_displaced_does_not_come_back_the_next_day():
    # Exactly the milestone day counts: the next day is a different number, so nothing is owed.
    assert daily_slot.choose(days_left=29, due_count=0, exam_on=True, revision_on=True) == Pick(Slot.THOUGHT)


def test_a_negative_or_zero_due_count_is_nothing_due():
    assert daily_slot.choose(days_left=None, due_count=0, exam_on=True, revision_on=True).slot is Slot.THOUGHT
    assert daily_slot.choose(days_left=None, due_count=-1, exam_on=True, revision_on=True).slot is Slot.THOUGHT
