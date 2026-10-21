"""
Tests for choice group resolution algorithm (ERD Section 3.5.5).
"""

from decimal import Decimal
from modules.mocktest.domain import choice


def test_resolve_choices_under_limit():
    # 6 questions in group, answer any 4 (k = 3 <= 4)
    groups = [
        {
            "key": "B-choice-1",
            "required_count": 4,
            "overflow_policy": "block",
            "positions": [21, 22, 23, 24, 25, 26],
        }
    ]
    answered = {
        21: {"answered": True, "marks_awarded": Decimal("5")},
        22: {"answered": True, "marks_awarded": Decimal("5")},
        23: {"answered": True, "marks_awarded": Decimal("5")},
    }

    res = choice.resolve_choices(groups, answered)
    g_res = res.resolution["groups"]["B-choice-1"]

    assert g_res["counted"] == [21, 22, 23]
    assert g_res["empty_slots"] == [24]  # 4 - 3 = 1 empty slot taken from 24
    assert g_res["not_counted"] == [25, 26]
    assert res.excluded_positions == {25, 26}


def test_resolve_choices_overflow_first_n():
    # 6 questions in group, answer any 4 (k = 5 > 4), policy = first_n
    groups = [
        {
            "key": "B-choice-1",
            "required_count": 4,
            "overflow_policy": "first_n",
            "positions": [21, 22, 23, 24, 25, 26],
        }
    ]
    answered = {
        21: {"answered": True, "marks_awarded": Decimal("5")},
        22: {"answered": True, "marks_awarded": Decimal("5")},
        23: {"answered": True, "marks_awarded": Decimal("5")},
        24: {"answered": True, "marks_awarded": Decimal("5")},
        25: {"answered": True, "marks_awarded": Decimal("5")},
    }

    res = choice.resolve_choices(groups, answered)
    g_res = res.resolution["groups"]["B-choice-1"]

    assert g_res["counted"] == [21, 22, 23, 24]
    assert g_res["not_counted"] == [25, 26]
    assert res.excluded_positions == {25, 26}


def test_resolve_choices_overflow_best_n():
    # 6 questions, answer any 4 (k = 5 > 4), policy = best_n
    groups = [
        {
            "key": "B-choice-1",
            "required_count": 4,
            "overflow_policy": "best_n",
            "positions": [21, 22, 23, 24, 25, 26],
        }
    ]
    answered = {
        21: {"answered": True, "marks_awarded": Decimal("2")},  # lowest marks
        22: {"answered": True, "marks_awarded": Decimal("5")},
        23: {"answered": True, "marks_awarded": Decimal("5")},
        24: {"answered": True, "marks_awarded": Decimal("4")},
        25: {"answered": True, "marks_awarded": Decimal("5")},
    }

    res = choice.resolve_choices(groups, answered)
    g_res = res.resolution["groups"]["B-choice-1"]

    # Best 4 should be 22 (5), 23 (5), 25 (5), 24 (4)
    assert g_res["counted"] == [22, 23, 24, 25]
    assert 21 in g_res["not_counted"]
    assert 26 in g_res["not_counted"]
    assert res.excluded_positions == {21, 26}
