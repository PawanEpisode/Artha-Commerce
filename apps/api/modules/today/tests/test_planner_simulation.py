"""The planner over many weeks, one morning at a time, with students who keep pace, miss a week, or stop (`planner_sim.py`)."""

from datetime import date, timedelta
from itertools import pairwise

import pytest

from modules.today.planner import capacity as cap
from modules.today.planner import constants as pc
from modules.today.planner import replan as rp

from .planner_sim import EXAM, PAPERS, START, Sim

ORDER = {"on_track": 0, "slightly_behind": 1, "at_risk": 2}
D = date


def triggers(sim: Sim):
    return [(e.day, e.trigger) for e in sim.events]


def more_time(options):
    return next((o for o in options if o["option"] == "more_time" and o["feasible"]), None)


def finish_dates(rows):
    return {(m.subject_key): m.target_date for m in rows if m.kind == "finish_reading" and m.status != "done"}


# ---- a student who keeps pace -----------------------------------------------------------------------------------------------


@pytest.mark.parametrize("style", ["parallel", "sequential"])
def test_a_student_who_keeps_pace_stays_on_track_for_twelve_weeks_and_is_only_replanned_on_mondays(style):
    sim = Sim.new(0.70, style=style).run(84, lambda d: 1.0)
    assert {health for _, health, _ in sim.daily_health} == {"on_track"}
    assert all(day.weekday() == pc.REPLAN_WEEKDAY for day, trigger in triggers(sim)) and len(sim.events) == 12
    assert {trigger for _, trigger in triggers(sim)} == {"weekly"}
    assert all(e.auto_apply and e.options == [] for e in sim.events)
    assert sim.read_done_on is not None and sim.read_done_on < sim.params.reading_deadline


def test_when_she_reads_the_way_the_plan_assumes_no_pending_date_moves_and_only_finished_papers_rebase_their_revisions():
    sim = Sim.new(0.70, style="parallel").run(84, lambda d: 1.0)
    for (_, before), (_, after) in pairwise(sim.stored_history):
        still_open = set(finish_dates(before)) & set(finish_dates(after))
        assert {k: finish_dates(before)[k] for k in still_open} == {k: finish_dates(after)[k] for k in still_open}
    # the mocks hang on the frozen deadline and never move for a student who keeps pace
    mocks = {tuple(m.target_date for m in rows if m.kind == "mock") for _, rows in sim.stored_history}
    assert len(mocks) == 1
    moved_kinds = set()
    for (_, before), (_, after) in pairwise(sim.stored_history):
        for b, a in zip(before, after, strict=False):
            if b.identity == a.identity and b.target_date != a.target_date and b.status == a.status:  # not a completion
                moved_kinds.add(b.kind)
    assert moved_kinds <= {"first_revision"}


def test_the_frozen_deadline_is_what_every_check_uses():
    sim = Sim.new(0.70).run(60, lambda d: 1.0)
    assert sim.params.reading_deadline == date(2026, 12, 18)
    assert all(row.target_date <= EXAM for _, rows in sim.stored_history for row in rows if row.status != "at_risk")


# ---- a student who misses a week --------------------------------------------------------------------------------------------


def missed_week(d: int) -> float:
    return 0.0 if 14 <= d < 21 else 1.0  # Oct 29 to Nov 4


def test_a_missed_week_triggers_on_the_second_missed_day_then_waits_out_the_three_day_gap():
    sim = Sim.new(0.70).run(35, missed_week)
    assert triggers(sim)[:6] == [
        (D(2026, 10, 19), "weekly"),
        (D(2026, 10, 26), "weekly"),
        (D(2026, 10, 31), "missed_days"),  # Oct 29 and 30 were missed
        (D(2026, 11, 3), "missed_days"),  # Nov 2 was a Monday but the last re-plan was 2 days ago
        (D(2026, 11, 9), "weekly"),
        (D(2026, 11, 16), "weekly"),
    ]
    assert D(2026, 11, 2) not in {e.day for e in sim.events} and D(2026, 11, 5) not in {e.day for e in sim.events}


def test_with_slack_a_missed_week_changes_dates_but_never_the_health_or_the_need_for_a_choice():
    sim = Sim.new(0.70).run(84, missed_week)
    assert {health for _, health, _ in sim.daily_health} == {"on_track"}
    assert all(e.auto_apply and e.options == [] for e in sim.events)
    assert sim.read_done_on < sim.params.reading_deadline


def test_a_missed_week_with_little_slack_turns_the_plan_slightly_behind_and_applies_nothing_until_the_student_chooses():
    sim = Sim.new(0.95).run(35, missed_week)  # nobody chooses
    pending = [e for e in sim.events if not e.auto_apply]
    assert pending, "the missed week should have used up a 5 percent slack"
    assert {e.health_after for e in pending} <= {"slightly_behind", "at_risk"}
    assert all([*e.options] == ["more_time", "skim_low_weight", "next_attempt"] for e in pending[:1])
    history = dict(sim.stored_history)
    for e in pending:  # the stored milestones the day a proposal was made are the ones from the day before
        assert history[e.day] == history[e.day - timedelta(days=1)]
    assert pending[0].day == D(2026, 11, 3)


def test_choosing_more_time_closes_the_gap_and_a_student_who_then_keeps_pace_finishes_reading_before_the_deadline():
    sim = Sim.new(0.95).run(84, missed_week, choose=more_time)
    chosen = [e for e in sim.events if e.chosen]
    assert chosen and all(e.chosen == "more_time" for e in chosen)
    assert pc.DAILY_MINUTES_MIN <= sim.params.daily_minutes <= pc.DAILY_MINUTES_MAX and sim.params.daily_minutes > 180
    assert sim.read_done_on is not None and sim.read_done_on < sim.params.reading_deadline
    assert sim.daily_health[-1][1] == "on_track"


def test_choosing_to_skim_halves_the_picked_chapters_and_also_gets_her_to_the_deadline():
    skim = lambda options: next((o for o in options if o["option"] == "skim_low_weight" and o["feasible"]), None)  # noqa: E731
    sim = Sim.new(0.95).run(84, missed_week, choose=skim)
    assert any(e.chosen == "skim_low_weight" for e in sim.events)
    assert sim.params.daily_minutes == 180 and sim.read_done_on < sim.params.reading_deadline


def test_looking_at_the_options_and_choosing_none_leaves_the_plan_alone_and_offers_again_after_the_gap():
    sim = Sim.new(0.95).run(60, missed_week, choose=lambda options: None)
    pending = [e for e in sim.events if not e.auto_apply]
    assert len(pending) >= 2 and all(e.chosen is None for e in pending)
    assert all((b.day - a.day).days >= pc.REPLAN_MIN_GAP_DAYS for a, b in pairwise(sim.events))
    assert sim.params.daily_minutes == 180


# ---- a student who stops ----------------------------------------------------------------------------------------------------


def test_a_student_who_stops_is_nagged_at_most_every_three_days_and_the_plan_only_gets_worse_until_the_exam():
    sim = Sim.new(0.90).run(94, lambda d: 1.0 if d < 5 else 0.0)
    assert len(sim.events) <= 94 // pc.REPLAN_MIN_GAP_DAYS + 1
    assert all(e.trigger in pc.AUTOMATIC_TRIGGERS for e in sim.events)
    assert all((b.day - a.day).days >= pc.REPLAN_MIN_GAP_DAYS for a, b in pairwise(sim.events))
    bands = [ORDER[h] for day, h, _ in sim.daily_health if day < EXAM]
    assert bands == sorted(bands) and bands[-1] == 2  # never better than yesterday, and at risk in the end
    history = dict(sim.stored_history)
    for e in sim.events:
        if not e.auto_apply:
            assert history[e.day] == history[e.day - timedelta(days=1)]  # nothing is applied behind her back


def test_once_the_reading_window_has_closed_the_options_stop_offering_more_time():
    sim = Sim.new(0.90).run(75, lambda d: 1.0 if d < 5 else 0.0)
    before = [e for e in sim.events if e.day < D(2026, 12, 18) and not e.auto_apply]
    after = [e for e in sim.events if e.day >= D(2026, 12, 18)]
    assert before and all("more_time" in e.options for e in before)
    assert after and all(e.options == ["skim_low_weight", "next_attempt"] for e in after)


def test_on_and_after_the_exam_day_the_plan_is_over_and_nothing_is_proposed():
    sim = Sim.new(0.90).run(80, lambda d: 1.0 if d < 5 else 0.0)
    for offset in (0, 1, 10):
        day = EXAM + timedelta(days=offset)
        params = sim.params.but(today=day)
        plan = rp.build_plan(params, PAPERS, sim.chapters())
        assert plan.health.health == "unknown" and plan.milestones == ()
        result = rp.replan(sim.stored, params, PAPERS, sim.chapters(), health_before="at_risk")
        assert (result.auto_apply, result.options, result.health_after) == (False, (), "unknown")
        assert len(result.orphaned) == len(sim.stored)  # reported, and the service decides: nothing is deleted here


# ---- the exam date moves ----------------------------------------------------------------------------------------------------


def test_moving_the_exam_later_recomputes_the_deadline_and_can_turn_a_late_plan_around():
    sim = Sim.new(0.95).run(30, lambda d: 1.0 if d < 5 else 0.0)  # she stopped; by Nov 14 the plan is behind
    today = START + timedelta(days=30)
    params = sim.params.but(today=today)
    assert rp.build_plan(params, PAPERS, sim.chapters()).health.health != "on_track"
    moved_exam = cap.freeze_deadline(params.but(exam_date=EXAM + timedelta(days=60), reading_deadline=None))
    result = rp.replan(sim.stored, moved_exam, PAPERS, sim.chapters(), health_before="slightly_behind")
    assert moved_exam.reading_deadline > sim.params.reading_deadline
    assert result.health_after == "on_track" and result.auto_apply
    kinds = {m.kind for m in result.moved}
    assert {"mock", "exam_week"} <= kinds and all(
        m.days > 0 for m in result.moved
    )  # everything is later: she lost 25 days, the exam gained 60
    assert rp.should_replan(today=today, missed_days=0, last_replanned_on=today, exam_date_changed=True) == "exam_date"
