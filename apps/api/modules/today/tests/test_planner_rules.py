"""Rule-by-rule tests of the pure planner: capacity, health bands, milestones, options, re-plan triggers and merging."""

import ast
import json
from datetime import date, timedelta
from pathlib import Path

import pytest

from modules.today.planner import capacity as cap
from modules.today.planner import constants as pc
from modules.today.planner import health as hl
from modules.today.planner import milestones as ms
from modules.today.planner import options as op
from modules.today.planner import replan as rp

TODAY = date(2026, 10, 15)
EXAM = date(2027, 1, 14)


def params(**over) -> cap.PlanParams:
    fields = dict(today=TODAY, exam_date=EXAM, daily_minutes=180)
    fields.update(over)
    return cap.PlanParams(**fields)


def papers(n=4) -> list[cap.PaperInput]:
    return [cap.PaperInput(f"p{i}", i, 100) for i in range(1, n + 1)]


def chapters(**minutes) -> list[cap.ChapterInput]:
    return [cap.ChapterInput(f"c-{k}", k, est_minutes=v) for k, v in minutes.items()]


# ---- the package is pure ----------------------------------------------------------------------------------------------------


def test_no_planner_module_imports_django_or_reads_the_clock_or_the_database():
    forbidden = {"django", "rest_framework", "random", "time"}
    folder = Path(cap.__file__).parent
    for path in folder.glob("*.py"):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [a.name.split(".")[0] for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                names = [node.module.split(".")[0]]
            assert not forbidden & set(names), f"{path.name} imports {names}"
        source = path.read_text()
        assert "date.today(" not in source and "datetime.now(" not in source, path.name


# ---- inputs -----------------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "field,value",
    [
        ("daily_minutes", 29),
        ("daily_minutes", 721),
        ("utilisation_pct", 29),
        ("utilisation_pct", 101),
        ("learn_share_pct", 9),
        ("lanes", 0),
        ("lanes", 5),
        ("exam_week_days", 8),
    ],
)
def test_inputs_outside_the_database_ranges_are_rejected(field, value):
    with pytest.raises(ValueError):
        params(**{field: value})


def test_a_stored_deadline_after_the_exam_is_rejected_and_freezing_is_idempotent():
    with pytest.raises(ValueError):
        params(reading_deadline=EXAM + timedelta(days=1))
    frozen = cap.freeze_deadline(params())
    assert (
        frozen.reading_deadline == date(2026, 12, 18) == cap.freeze_deadline(frozen.but(today=TODAY)).reading_deadline
    )


def test_a_stored_deadline_wins_over_the_formula_until_the_exam_day_and_applying_next_attempt_forgets_it():
    p = cap.freeze_deadline(params())
    later = p.but(today=TODAY + timedelta(days=30))
    assert cap.reading_deadline(later) == date(2026, 12, 18) != cap.formula_deadline(later)
    assert cap.reading_deadline(later.but(today=EXAM)) is None
    moved, _ = op.apply_option(p, [], {"option": "next_attempt", "exam_date": "2027-05-14"})
    assert moved.reading_deadline is None and moved.exam_date == date(2027, 5, 14)


# ---- capacity ---------------------------------------------------------------------------------------------------------------


def test_the_reading_buffer_is_14_days_or_30_percent_of_the_runway_half_up():
    assert cap.reading_buffer_days(10) == 14
    assert cap.reading_buffer_days(46) == 14  # 13.8 rounds to 14
    assert cap.reading_buffer_days(48) == 14  # 14.4 rounds to 14
    assert cap.reading_buffer_days(50) == 15  # 15.0
    assert cap.reading_buffer_days(85) == 26  # 25.5
    assert cap.reading_buffer_days(55) == 17  # 16.5 rounds up; Python's round() would give 16 (half to even)
    assert cap.reading_buffer_days(75) == 23  # 22.5, round() would give 22
    assert cap.reading_buffer_days(182) == 55  # 54.6


def test_today_counts_as_a_full_study_day():
    assert cap.runway_days(date(2026, 10, 19), date(2026, 10, 20)) == 1
    assert cap.runway_days(date(2026, 10, 20), date(2026, 10, 20)) == 0
    assert cap.runway_days(date(2026, 10, 21), date(2026, 10, 20)) == 0
    p = params(exam_date=date(2026, 12, 14))  # 60 days: buffer 18, deadline Nov 26, 42 reading days
    assert (cap.reading_deadline(p), cap.learn_days(p)) == (date(2026, 11, 26), 42)


def test_capacity_is_floored_once_at_the_end():
    p = params(daily_minutes=61, utilisation_pct=33, learn_share_pct=77)
    assert cap.reading_capacity(p) == cap.learn_days(p) * 61 * 33 * 77 // 10_000


def test_remaining_is_the_unread_share_rounded_up_per_chapter_with_60_when_the_estimate_is_missing():
    rows = [
        cap.ChapterInput("a", "p1", est_minutes=90, read_pct=50),  # 45
        cap.ChapterInput("b", "p1", est_minutes=None, read_pct=0),  # 60 default
        cap.ChapterInput("c", "p1", est_minutes=7, read_pct=50),  # 3.5 -> 4
        cap.ChapterInput("d", "p2", est_minutes=100, read_pct=100),  # read
        cap.ChapterInput("e", "p2", est_minutes=100, excluded=True),  # not planned
        cap.ChapterInput("f", "p2", est_minutes=100, read_pct=130),  # a coverage above 100 counts as read
    ]
    assert [cap.chapter_remaining(c) for c in rows] == [45, 60, 4, 0, 0, 0]
    assert cap.remaining_by_paper(rows) == {"p1": 109, "p2": 0}
    assert cap.remaining_minutes(rows) == 109


def test_the_exam_day_and_later_leave_no_window():
    c = cap.compute_capacity(params(exam_date=TODAY), chapters(p1=100))
    assert (c.runway_days, c.reading_deadline, c.revise_until, c.capacity_minutes, c.shortfall_minutes) == (
        0,
        None,
        None,
        0,
        100,
    )


# ---- health -----------------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "shortfall,capacity,band",
    [
        (0, 1000, "on_track"),
        (0, 0, "on_track"),
        (1, 1000, "slightly_behind"),
        (100, 1000, "slightly_behind"),  # exactly 10 percent
        (101, 1000, "at_risk"),
        (1, 0, "at_risk"),  # no capacity at all
        (1200, 6000, "at_risk"),
    ],
)
def test_health_bands(shortfall, capacity, band):
    assert hl.classify(shortfall, capacity) == band


def test_a_plan_with_everything_read_is_on_track_and_a_finished_plan_is_unknown():
    done = hl.assess(remaining_minutes=0, capacity_minutes=500)
    assert (done.health, done.shortfall_minutes) == ("on_track", 0)
    over = rp.build_plan(params(exam_date=TODAY), papers(), chapters(p1=100))
    assert over.health.health == "unknown" and over.milestones == ()


# ---- milestones -------------------------------------------------------------------------------------------------------------


def test_papers_go_to_the_least_loaded_lane_and_the_first_lane_wins_a_tie():
    placed = ms.assign_lanes(papers(), {"p1": 1800, "p2": 1500, "p3": 1200, "p4": 900}, 2)
    assert [(p.subject_key, p.lane, p.lane_minutes) for p in placed] == [
        ("p1", 0, 1800),
        ("p2", 1, 1500),
        ("p3", 1, 2700),
        ("p4", 0, 2700),
    ]
    assert [p.lane for p in ms.assign_lanes(papers(3), {"p1": 0, "p2": 0, "p3": 0}, 2)] == [0, 0, 0]  # nothing to carry


def test_a_single_lane_reads_papers_one_after_the_other_at_the_full_rate():
    p = params(lanes=1)
    plan = rp.build_plan(p, papers(2), chapters(p1=882, p2=882))
    finish = {m.subject_key: m.target_date for m in plan.milestones if m.kind == "finish_reading"}
    # 180 x 0.49 = 88.2 a day: 882 minutes is exactly 10 days, 1764 is 20
    assert finish == {"p1": TODAY + timedelta(days=9), "p2": TODAY + timedelta(days=19)}


def test_a_paper_that_is_already_read_is_done_today():
    plan = rp.build_plan(params(), papers(2), chapters(p1=0, p2=500))
    row = next(m for m in plan.milestones if (m.kind, m.subject_key) == ("finish_reading", "p1"))
    assert (row.status, row.target_date, row.remaining_minutes) == ("done", TODAY, 0)


def test_dates_run_past_their_windows_honestly_and_stay_in_order():
    plan = rp.build_plan(params(), papers(), chapters(p1=4000, p2=3000, p3=2000, p4=1000))
    by = {m.identity: m for m in plan.milestones}
    deadline, revise = plan.capacity.reading_deadline, plan.capacity.revise_until
    for key in ("p1", "p2", "p3", "p4"):
        f, r, m = (by[(k, key)] for k in ("finish_reading", "first_revision", "mock"))
        assert f.target_date < r.target_date < m.target_date
        assert (f.status == "at_risk") == (f.target_date >= deadline)
        assert (r.status == "at_risk") == (r.target_date > revise)
        assert (m.status == "at_risk") == (m.target_date > revise)
    assert by[("finish_reading", "p1")].target_date > plan.capacity.reading_deadline  # not clamped


def test_the_mock_is_a_week_after_the_reading_deadline_when_the_plan_fits():
    plan = rp.build_plan(params(), papers(), chapters(p1=100, p2=100, p3=100, p4=100))
    deadline = plan.capacity.reading_deadline
    assert {m.target_date for m in plan.milestones if m.kind == "mock"} == {deadline + timedelta(days=7)}


def test_exam_week_starts_seven_days_before_the_exam_and_has_no_paper():
    plan = rp.build_plan(params(), papers(), chapters(p1=100))
    row = next(m for m in plan.milestones if m.kind == "exam_week")
    assert (row.subject_key, row.target_date) == ("", EXAM - timedelta(days=7))
    assert sum(1 for m in plan.milestones if m.kind == "exam_week") == 1


def test_papers_without_marks_or_numbers_still_get_a_stable_order():
    mixed = [
        cap.PaperInput("zeta"),
        cap.PaperInput("alpha"),
        cap.PaperInput("beta", 2, 100),
        cap.PaperInput("gamma", 1, 100),
    ]
    assert [p.subject_key for p in ms.reading_order(mixed)] == ["gamma", "beta", "alpha", "zeta"]


# ---- options ----------------------------------------------------------------------------------------------------------------


def test_more_time_is_the_smallest_daily_figure_that_closes_the_gap():
    p = params()
    required = op.more_time_option(p, 10_000)["daily_minutes"]
    assert (
        cap.reading_capacity(p.but(daily_minutes=required))
        >= 10_000
        > cap.reading_capacity(p.but(daily_minutes=required - 1))
    )


def test_more_time_past_12_hours_a_day_is_not_feasible_and_no_reading_days_means_no_option():
    huge = op.more_time_option(params(), 200_000)
    assert huge["feasible"] is False and huge["daily_minutes"] > pc.DAILY_MINUTES_MAX
    assert op.more_time_option(params(exam_date=TODAY + timedelta(days=5)), 100) is None


def test_skimming_starts_with_the_lowest_marks_per_minute_and_breaks_ties_by_key():
    rows = [
        cap.ChapterInput("z", "p1", est_minutes=100, marks_weight=10),  # 0.1
        cap.ChapterInput("b", "p1", est_minutes=100, marks_weight=5),  # 0.05
        cap.ChapterInput("a", "p1", est_minutes=200, marks_weight=10),  # 0.05
        cap.ChapterInput("one", "p1", est_minutes=1, marks_weight=0),  # a single minute saves nothing
        cap.ChapterInput("read", "p1", est_minutes=100, read_pct=100, marks_weight=0),
    ]
    assert [(key, saved) for _, key, saved in op.skim_candidates(rows)] == [("a", 100), ("b", 50), ("z", 50)]
    picked = op.skim_option(rows, shortfall=120)
    assert (picked["chapters"], picked["saved_minutes"], picked["feasible"]) == (["a", "b"], 150, True)
    assert op.skim_option(rows, shortfall=500)["feasible"] is False


def test_a_chapter_without_a_weight_is_not_skimmed_before_one_with_a_low_weight():
    rows = [
        cap.ChapterInput("a", "p1", est_minutes=100, marks_weight=0.2),
        cap.ChapterInput("b", "p1", est_minutes=100),
    ]
    assert [key for _, key, _ in op.skim_candidates(rows)] == ["a", "b"]


def test_skimmed_chapters_count_half_and_cannot_be_skimmed_twice():
    rows = [cap.ChapterInput("a", "p1", est_minutes=101, skim=True)]
    assert cap.chapter_remaining(rows[0]) == 51 and op.skim_candidates(rows) == []


def test_next_attempt_needs_a_later_date():
    p, rows = params(), chapters(p1=9000)
    assert op.next_attempt_option(p, rows, None)["feasible"] is False
    assert op.next_attempt_option(p, rows, EXAM)["feasible"] is False  # the same date is not a later attempt
    later = op.next_attempt_option(p, rows, date(2027, 5, 14))
    assert later["feasible"] is True and later["exam_date"] == "2027-05-14"


def test_apply_option_with_none_or_nonsense_changes_nothing():
    p, rows = params(), chapters(p1=9000)
    assert op.apply_option(p, rows, {"option": "none"}) == (p, rows)
    assert op.apply_option(p, rows, {}) == (p, rows)


# ---- when to re-plan --------------------------------------------------------------------------------------------------------

MONDAY = date(2026, 10, 19)
TUESDAY = date(2026, 10, 20)


def test_missed_days_count_back_from_yesterday_and_stop_at_the_first_active_day_or_the_plan_start():
    active = {date(2026, 10, 10), date(2026, 10, 13)}
    assert rp.consecutive_missed_days(active, date(2026, 10, 14), date(2026, 10, 1)) == 0  # studied on the 13th
    assert rp.consecutive_missed_days(active, date(2026, 10, 17), date(2026, 10, 1)) == 3  # 14th, 15th, 16th
    assert rp.consecutive_missed_days(active, date(2026, 10, 17), date(2026, 10, 15)) == 2  # the plan began on the 15th
    assert rp.consecutive_missed_days(active, date(2026, 10, 15), date(2026, 10, 15)) == 0  # nothing before the plan
    assert rp.consecutive_missed_days({TODAY}, TODAY, date(2026, 10, 1)) == 14  # today's own activity does not count


@pytest.mark.parametrize(
    "kwargs,expected",
    [
        (dict(today=TUESDAY, missed_days=1, last_replanned_on=None), None),
        (dict(today=TUESDAY, missed_days=2, last_replanned_on=None), "missed_days"),
        (dict(today=TUESDAY, missed_days=5, last_replanned_on=TUESDAY - timedelta(days=3)), "missed_days"),
        (dict(today=TUESDAY, missed_days=5, last_replanned_on=TUESDAY - timedelta(days=2)), None),  # the 3-day gap
        (dict(today=MONDAY, missed_days=0, last_replanned_on=None), "weekly"),
        (dict(today=MONDAY, missed_days=2, last_replanned_on=None), "missed_days"),  # the sharper reason wins
        (dict(today=MONDAY, missed_days=0, last_replanned_on=MONDAY - timedelta(days=2)), None),
        (dict(today=MONDAY, missed_days=0, last_replanned_on=MONDAY - timedelta(days=7)), "weekly"),
        (dict(today=TUESDAY, missed_days=0, last_replanned_on=None, manual=True), "manual"),
        (dict(today=TUESDAY, missed_days=0, last_replanned_on=TUESDAY, exam_date_changed=True), "exam_date"),
        (dict(today=TUESDAY, missed_days=0, last_replanned_on=TUESDAY, scheme_switched=True), "scheme_switch"),
        (dict(today=TUESDAY, missed_days=9, last_replanned_on=TUESDAY, manual=True, exam_date_changed=True), "manual"),
    ],
)
def test_replan_triggers(kwargs, expected):
    assert rp.should_replan(**kwargs) == expected


# ---- the re-plan ------------------------------------------------------------------------------------------------------------


def test_replanning_twice_with_the_same_inputs_moves_nothing_the_second_time():
    p, ps, ch = params(), papers(), chapters(p1=1800, p2=1500, p3=1200, p4=900)
    first = rp.replan(rp.build_plan(p, ps, ch).milestones, p.but(today=TODAY + timedelta(days=5)), ps, ch)
    assert first.moved_count > 0
    again = rp.replan(first.plan.milestones, p.but(today=TODAY + timedelta(days=5)), ps, ch)
    assert again.moved == () and again.plan.milestones == first.plan.milestones


def test_done_and_dropped_milestones_are_never_moved_or_rewritten():
    p, ps, ch = params(), papers(2), chapters(p1=1800, p2=1500)
    stored = list(rp.build_plan(p, ps, ch).milestones)
    stored = [
        ms.MilestoneRow(
            m.subject_key,
            m.kind,
            m.target_date,
            m.remaining_minutes,
            "done"
            if m.identity == ("finish_reading", "p1")
            else ("dropped" if m.identity == ("mock", "p2") else m.status),
            m.sort_order,
        )
        for m in stored
    ]
    result = rp.replan(stored, p.but(today=TODAY + timedelta(days=6)), ps, ch)
    kept = {m.identity: m for m in result.plan.milestones}
    original = {m.identity: m for m in stored}
    for identity in (("finish_reading", "p1"), ("mock", "p2")):
        assert (kept[identity].target_date, kept[identity].status) == (
            original[identity].target_date,
            original[identity].status,
        )
    assert {(m.kind, m.subject_key) for m in result.moved}.isdisjoint({("finish_reading", "p1"), ("mock", "p2")})


def test_a_paper_that_has_just_been_read_is_completed_not_moved_and_its_revision_follows_the_day_it_finished():
    p, ps = params(), papers(2)
    before = chapters(p1=600, p2=600)
    stored = rp.build_plan(p, ps, before).milestones
    day = TODAY + timedelta(days=10)
    finished = [cap.ChapterInput("c-p1", "p1", est_minutes=600, read_pct=100), before[1]]
    result = rp.replan(stored, p.but(today=day), ps, finished)
    assert [(m.kind, m.subject_key, m.status, m.target_date) for m in result.completed] == [
        ("finish_reading", "p1", "done", day)
    ]
    assert ("finish_reading", "p1") not in {(m.kind, m.subject_key) for m in result.moved}
    done = {m.identity: m for m in result.plan.milestones}
    assert done[("finish_reading", "p1")].status == "done" and done[
        ("first_revision", "p1")
    ].target_date == day + timedelta(days=7)
    # a week later the paper is still done on that day and its revision does not slide with the calendar
    later = rp.replan(result.plan.milestones, p.but(today=day + timedelta(days=7)), ps, finished)
    again = {m.identity: m for m in later.plan.milestones}
    assert later.completed == () and again[("finish_reading", "p1")].target_date == day
    assert again[("first_revision", "p1")].target_date == day + timedelta(days=7)
    assert ("first_revision", "p1") not in {(m.kind, m.subject_key) for m in later.moved}


def test_a_milestone_that_is_no_longer_computed_is_reported_never_dropped_and_a_new_paper_is_added():
    p, ch = params(), chapters(p1=500, p2=500, p3=500)
    stored = rp.build_plan(p, papers(3), ch).milestones
    result = rp.replan(stored, p, papers(2) + [cap.PaperInput("p9", 9, 100)], ch + chapters(p9=300))
    assert {m.subject_key for m in result.orphaned} == {"p3"} and len(result.orphaned) == 3
    assert {m.subject_key for m in result.added} == {"p9"} and len(result.added) == 3


def test_a_replan_reports_health_before_and_after_and_proposes_without_applying_when_short():
    p, ps = params(), papers()
    ok = chapters(p1=500, p2=500, p3=500, p4=500)
    behind = chapters(p1=4000, p2=3000, p3=2000, p4=1000)
    stored = rp.build_plan(p, ps, ok).milestones
    result = rp.replan(stored, p, ps, behind, health_before="on_track", shortfall_before=0)
    assert (result.health_before, result.health_after) == ("on_track", "at_risk")
    assert (result.shortfall_before, result.shortfall_after) == (0, 4356)
    assert result.auto_apply is False and result.options and result.moved


def test_after_the_exam_a_replan_proposes_nothing_and_orphans_everything():
    p, ps, ch = params(), papers(2), chapters(p1=500, p2=500)
    stored = rp.build_plan(p, ps, ch).milestones
    result = rp.replan(stored, p.but(today=EXAM), ps, ch)
    assert (result.auto_apply, result.options, result.health_after) == (False, (), "unknown")
    assert len(result.orphaned) == len(stored) and result.plan.milestones == ()


def test_the_summary_has_the_erd_shape_and_stays_under_8_kb_even_with_a_huge_skim_list():
    p, ps = params(), papers(8)
    many = [
        cap.ChapterInput(f"chapter-{i:04d}-" + "x" * 30, f"p{1 + i % 8}", est_minutes=120, marks_weight=1 + i % 7)
        for i in range(400)
    ]
    stored = rp.build_plan(p, ps, [cap.ChapterInput("k", "p1", est_minutes=10)]).milestones
    result = rp.replan(
        stored, p.but(today=TODAY + timedelta(days=30), daily_minutes=60), ps, many, next_exam_date=date(2027, 5, 1)
    )
    summary = rp.summary_json(result)
    assert set(summary) == {"v", "moved", "options"} and summary["v"] == 1
    assert len(json.dumps(summary)) <= pc.SUMMARY_MAX_CHARS
    assert all(set(m) == {"subject_key", "kind", "from", "to"} for m in summary["moved"])
    skim = next(o for o in summary["options"] if o["option"] == "skim_low_weight")
    assert skim["chapter_count"] > len(skim["chapters"])  # the count stays exact, the list is cut


def test_the_summary_drops_moved_entries_last_resort_to_fit():
    big = rp.ReplanResult(
        plan=rp.build_plan(params(), papers(), chapters(p1=1)),
        health_before="on_track",
        health_after="on_track",
        shortfall_before=0,
        shortfall_after=0,
        moved=tuple(rp.Moved("k" * 60, "finish_reading", TODAY, TODAY + timedelta(days=1)) for _ in range(500)),
        completed=(),
        added=(),
        orphaned=(),
        options=(),
        auto_apply=True,
    )
    out = rp.summary_json(big)
    assert len(json.dumps(out)) <= pc.SUMMARY_MAX_CHARS and 0 < len(out["moved"]) <= pc.SUMMARY_MAX_MOVED
