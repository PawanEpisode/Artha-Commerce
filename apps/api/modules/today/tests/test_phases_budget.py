"""Phases, multipliers, budget, focus papers, comeback, estimates (PRD 5.5)."""

from datetime import date

import pytest

from modules.today.domain import budget, estimates, phases
from modules.today.domain.constants import GROUPS

# ---- phases -----------------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("days", "phase"),
    [
        (None, "steady"),
        (400, "build"),
        (91, "build"),
        (90, "consolidate"),
        (31, "consolidate"),
        (30, "sprint"),
        (11, "sprint"),
        (10, "final"),
        (1, "final"),
        (0, "post_exam"),
        (-12, "post_exam"),
    ],
)
def test_phase_boundaries(days, phase):
    assert phases.phase_for(days) == phase


def test_days_to_exam_counts_calendar_days():
    assert phases.days_to_exam(date(2026, 12, 5), date(2026, 10, 14)) == 52
    assert phases.days_to_exam(date(2026, 10, 14), date(2026, 10, 14)) == 0
    assert phases.days_to_exam(date(2026, 10, 1), date(2026, 10, 14)) == -13
    assert phases.days_to_exam(None, date(2026, 10, 14)) is None


def test_the_multiplier_table_matches_the_prd():
    assert phases.multiplier("final", "learn") == 20 and phases.multiplier("final", "revise") == 150
    assert phases.multiplier("consolidate", "practice") == 120 and phases.multiplier("sprint", "news") == 140
    assert phases.multiplier("build", "exam") == 60 and phases.multiplier("steady", "exam") == 100


def test_every_phase_with_a_plan_covers_every_group():
    for phase in ("steady", "build", "consolidate", "sprint", "final"):
        assert {g: phases.multiplier(phase, g) for g in GROUPS}


def test_post_exam_has_no_multipliers_and_unknown_groups_are_bugs():
    with pytest.raises(ValueError):
        phases.multiplier("post_exam", "learn")
    with pytest.raises(ValueError):
        phases.multiplier("steady", "mystery")


# ---- budget -----------------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("daily_minutes", "expected"),
    [
        (None, 60),  # unknown hours: the first plan is "about 1 h"
        (0, 60),
        (60, 30),  # 21 -> 20 -> floor 30
        (120, 40),  # 42 -> 40
        (180, 65),  # 63 -> 65
        (240, 85),  # 84 -> 85
        (360, 120),  # 126 -> 125 -> cap 120
        (900, 120),
    ],
)
def test_auto_budget(daily_minutes, expected):
    assert budget.auto_budget(daily_minutes) == expected


def test_auto_budget_rounds_half_up_to_five():
    assert budget.auto_budget(150) == 55  # 52.5 -> 55
    assert budget.auto_budget(130) == 45  # 45.5 -> 45


def test_a_setting_wins_and_is_clamped():
    assert budget.budget_for(setting_minutes=90, daily_minutes=360) == (90, "setting")
    assert budget.budget_for(setting_minutes=5, daily_minutes=None) == (15, "setting")
    assert budget.budget_for(setting_minutes=999, daily_minutes=None) == (240, "setting")
    assert budget.budget_for(setting_minutes=None, daily_minutes=360) == (120, "auto")


@pytest.mark.parametrize(("b", "f"), [(30, 1), (59, 1), (60, 2), (65, 2), (99, 2), (100, 3), (120, 3), (240, 3)])
def test_focus_papers_rounds_half_up_and_stays_between_one_and_three(b, f):
    assert budget.focus_papers(b) == f


def test_focus_papers_setting_may_go_to_four():
    assert budget.focus_papers(30, setting=4) == 4
    assert budget.focus_papers(30, setting=9) == 4
    assert budget.focus_papers(240, setting=1) == 1


def test_comeback_budget_is_sixty_percent_never_under_the_floor():
    assert budget.comeback_budget(65) == 39
    assert budget.comeback_budget(60) == 36
    assert budget.comeback_budget(15) == 10  # 9 would break the plan's budget check


def test_comeback_needs_three_missed_days_and_a_past():
    assert budget.is_comeback([False, False, False], had_activity_before=True) is True
    assert budget.is_comeback([False, False, False, True], had_activity_before=True) is True
    assert budget.is_comeback([False, False, True], had_activity_before=True) is False
    assert budget.is_comeback([False, False], had_activity_before=True) is False  # not enough history to say
    assert (
        budget.is_comeback([False, False, False], had_activity_before=False) is False
    )  # a new student is not coming back
    assert budget.task_cap(True) == 5 and budget.task_cap(False) == 8


# ---- estimates --------------------------------------------------------------------------------------------------------------


def test_estimate_bounds_differ_for_providers_and_own_tasks():
    assert estimates.valid_estimate(90) and not estimates.valid_estimate(91)
    assert estimates.valid_estimate(180, own=True) and not estimates.valid_estimate(181, own=True)
    assert not estimates.valid_estimate(0) and not estimates.valid_estimate(True) and not estimates.valid_estimate(5.5)
    assert (
        estimates.clamp_estimate(500) == 90
        and estimates.clamp_estimate(-3) == 1
        and estimates.clamp_estimate(500, own=True) == 180
    )


def test_default_estimates_per_kind_round_up_to_whole_minutes():
    assert estimates.mcq_minutes(5) == 8  # 7.5
    assert estimates.recall_minutes(12) == 6
    assert estimates.recall_minutes(1) == 1  # never zero
    assert estimates.practical_minutes(10) == 20
    assert estimates.mcq_minutes(500) == 90  # clamped to the provider bound
