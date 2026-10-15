"""The planner against numbers worked out by hand from the ERD formulas (`fixtures/planner_golden.json`).

The derivation of each scenario is written next to its numbers in the fixture. There is no planner worked example in the PRD (5.6
is the composition one), so these are the founder's to sanity-check.
"""

import json
from datetime import date
from pathlib import Path

import pytest

from modules.today.planner import capacity as cap
from modules.today.planner import health as hl
from modules.today.planner import milestones as ms
from modules.today.planner import options as op
from modules.today.planner import replan as rp

FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "planner_golden.json").read_text())


def load(name: str):
    raw = FIXTURE[name]
    params = cap.PlanParams(
        today=date.fromisoformat(raw["params"]["today"]),
        exam_date=date.fromisoformat(raw["params"]["exam_date"]),
        daily_minutes=raw["params"]["daily_minutes"],
    )
    papers = [cap.PaperInput(**p) for p in raw["papers"]]
    chapters = [cap.ChapterInput(**c) for c in raw["chapters"]]
    next_date = date.fromisoformat(raw["next_exam_date"]) if raw.get("next_exam_date") else None
    return raw, params, papers, chapters, next_date


def rows(plan: rp.PlanComputation):
    return [
        {
            "subject_key": m.subject_key,
            "kind": m.kind,
            "target_date": m.target_date.isoformat(),
            "remaining_minutes": m.remaining_minutes,
            "status": m.status,
        }
        for m in plan.milestones
    ]


@pytest.mark.parametrize("name", ["on_track", "at_risk", "short_runway"])
def test_the_plan_matches_the_hand_worked_numbers(name):
    raw, params, papers, chapters, _ = load(name)
    plan = rp.build_plan(params, papers, chapters)
    expected = raw["expected"]
    capacity = plan.capacity
    assert capacity.capacity_minutes == expected["capacity_minutes"]
    assert capacity.remaining_minutes == expected["remaining_minutes"]
    assert capacity.shortfall_minutes == expected["shortfall_minutes"]
    assert plan.health.health == expected["health"]
    for field in ("runway_days", "learn_days"):
        if field in expected:
            assert getattr(capacity, field) == expected[field]
    for field in ("reading_deadline", "revise_until"):
        if field in expected:
            assert getattr(capacity, field).isoformat() == expected[field]
    assert rows(plan) == expected["milestones"]
    assert [m.sort_order for m in plan.milestones] == list(range(len(plan.milestones)))


@pytest.mark.parametrize("name", ["at_risk", "short_runway"])
def test_the_options_match_the_hand_worked_numbers(name):
    raw, params, _, chapters, next_date = load(name)
    assert op.compute_options(params, chapters, next_date) == raw["expected"]["options"]


def test_a_plan_that_fits_offers_no_options():
    _, params, _, chapters, next_date = load("on_track")
    assert op.compute_options(params, chapters, next_date) == []


def test_the_prd_health_example_is_20_hours_short_and_at_risk():
    ex = FIXTURE["fr_f13_48"]
    health = hl.assess(remaining_minutes=ex["remaining_minutes"], capacity_minutes=ex["capacity_minutes"])
    assert (health.health, health.shortfall_minutes, health.shortfall_hours) == (
        ex["health"],
        ex["shortfall_minutes"],
        ex["shortfall_hours"],
    )


def replan_scenario(name: str):
    """Create the plan on `created_on` (reading deadline frozen), re-plan on `today`, and return what the fixture expects."""
    raw = FIXTURE[name]
    source = raw if "params" in raw else FIXTURE[raw["use_plan"]]  # a scenario may reuse another one's inputs
    params = cap.PlanParams(
        today=date.fromisoformat(source["params"]["today"]),
        exam_date=date.fromisoformat(source["params"]["exam_date"]),
        daily_minutes=source["params"]["daily_minutes"],
    )
    papers = [cap.PaperInput(**p) for p in source["papers"]]
    chapters = [cap.ChapterInput(**c) for c in source["chapters"]]
    params = cap.freeze_deadline(params.but(today=date.fromisoformat(raw["created_on"])))
    stored = rp.build_plan(params, papers, chapters)
    result = rp.replan(
        stored.milestones,
        params.but(today=date.fromisoformat(raw["today"])),
        papers,
        chapters,
        health_before=stored.health.health,
        shortfall_before=stored.health.shortfall_minutes,
    )
    moved = [(m.subject_key, m.kind, m.from_date.isoformat(), m.to_date.isoformat()) for m in result.moved]
    return raw["expected"], stored, result, moved


def test_three_missed_days_with_slack_shift_the_dates_that_depend_on_the_start_and_say_what_moved():
    exp, stored, result, moved = replan_scenario("replan_with_slack")
    assert stored.health.health == "on_track"
    assert result.plan.capacity.capacity_minutes == exp["capacity_minutes"]
    assert (result.health_after, result.auto_apply, result.moved_count) == (exp["health"], True, exp["moved_count"])
    assert moved == [tuple(m) for m in exp["moved"]]
    assert {m.kind for m in result.moved} == {
        "finish_reading",
        "first_revision",
    }  # mocks and exam week hang on the frozen deadline
    assert result.added == () and result.orphaned == ()


def test_three_missed_days_use_up_the_slack_when_the_deadline_does_not_move():
    """The same plan with no slack: the frozen deadline means missed days are not hidden, the plan turns slightly behind."""
    exp, stored, result, moved = replan_scenario("replan_missed_days_make_it_short")
    assert stored.health.health == "on_track" and stored.capacity.reading_deadline == date(2026, 12, 18)
    assert result.plan.capacity.reading_deadline == date(2026, 12, 18)  # frozen, not recomputed from the shorter runway
    assert result.plan.capacity.capacity_minutes == exp["capacity_minutes"]
    assert (result.health_after, result.shortfall_after, result.auto_apply) == (
        exp["health"],
        exp["shortfall_minutes"],
        False,
    )
    assert (result.health_before, result.shortfall_before) == ("on_track", 0)
    assert moved == [tuple(m) for m in exp["moved"]] and result.moved_count == exp["moved_count"]
    at_risk = {m.subject_key for m in result.plan.milestones if m.kind == "finish_reading" and m.status == "at_risk"}
    assert at_risk == set(exp["at_risk_finishes"])
    assert list(result.options) == exp["options"]


def test_recomputing_the_deadline_would_hide_the_missed_days_which_is_why_it_is_frozen():
    _, params, papers, chapters, _ = load("on_track")
    later = params.but(today=date(2026, 10, 18))
    assert cap.formula_deadline(later) == date(2026, 12, 19)  # the formula slides a day later in three days
    assert (
        cap.reading_capacity(later)
        == 5468
        > cap.reading_capacity(cap.freeze_deadline(params).but(today=later.today))
        == 5380
    )


def test_an_infeasible_plan_replans_to_a_proposal_with_three_options_and_applies_nothing():
    raw, params, papers, chapters, next_date = load("at_risk")
    result = rp.replan([], params, papers, chapters, next_exam_date=next_date)
    assert result.auto_apply is False
    assert [o["option"] for o in result.options] == ["more_time", "skim_low_weight", "next_attempt"]
    assert rows(result.plan) == raw["expected"]["milestones"]


def test_the_chosen_option_closes_the_gap_when_it_is_feasible():
    _, params, papers, chapters, next_date = load("at_risk")
    for option in op.compute_options(params, chapters, next_date):
        assert option["feasible"] is True
        new_params, new_chapters = op.apply_option(params, chapters, option)
        assert rp.build_plan(new_params, papers, new_chapters).health.shortfall_minutes == 0, option["option"]


def test_the_golden_papers_are_read_in_marks_then_paper_order():
    _, _, papers, chapters, _ = load("on_track")
    shuffled = [papers[2], papers[0], papers[3], papers[1]]
    assert [p.subject_key for p in ms.reading_order(shuffled)] == ["p1", "p2", "p3", "p4"]
    big = [*papers[:3], cap.PaperInput("big", 9, 150)]
    assert ms.reading_order(big)[0].subject_key == "big"
