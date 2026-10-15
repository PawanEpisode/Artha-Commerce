"""Invariants of the planner over random plans (hypothesis): they must hold whatever a student's inputs and chapters are."""

import json
from datetime import date, timedelta

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from modules.today.planner import capacity as cap
from modules.today.planner import constants as pc
from modules.today.planner import health as hl
from modules.today.planner import milestones as ms
from modules.today.planner import options as op
from modules.today.planner import replan as rp

TODAY = date(2026, 10, 15)
SETTINGS = settings(
    max_examples=150, deadline=None, suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large]
)


@st.composite
def plans(draw, min_days=0, max_days=420):
    today = TODAY + timedelta(days=draw(st.integers(0, 30)))
    params = cap.PlanParams(
        today=today,
        exam_date=today + timedelta(days=draw(st.integers(min_days, max_days))),
        daily_minutes=draw(st.integers(pc.DAILY_MINUTES_MIN, pc.DAILY_MINUTES_MAX)),
        utilisation_pct=draw(st.integers(pc.UTILISATION_PCT_MIN, pc.UTILISATION_PCT_MAX)),
        learn_share_pct=draw(st.integers(pc.LEARN_SHARE_PCT_MIN, pc.LEARN_SHARE_PCT_MAX)),
        lanes=draw(st.integers(1, pc.LANES_MAX)),
    )
    n_papers = draw(st.integers(1, 8))
    papers = [
        cap.PaperInput(
            f"p{i}", draw(st.one_of(st.none(), st.integers(1, 20))), draw(st.one_of(st.none(), st.integers(0, 150)))
        )
        for i in range(n_papers)
    ]
    chapters = []
    for i in range(n_papers):
        for j in range(draw(st.integers(0, 6))):
            chapters.append(
                cap.ChapterInput(
                    key=f"p{i}-c{j}",
                    subject_key=f"p{i}",
                    est_minutes=draw(st.one_of(st.none(), st.integers(0, 600))),
                    read_pct=draw(st.integers(0, 100)),
                    marks_weight=draw(st.sampled_from([0.0, 0.5, 1.0, 2.5, 7.0, 12.5])),
                    excluded=draw(st.integers(0, 9)) == 0,
                )
            )
    return params, papers, chapters


# ---- capacity and health ----------------------------------------------------------------------------------------------------


@SETTINGS
@given(plans())
def test_capacity_is_never_negative_and_the_shortfall_is_exact(plan):
    params, _, chapters = plan
    c = cap.compute_capacity(params, chapters)
    assert c.capacity_minutes >= 0 and c.remaining_minutes >= 0 and c.learn_days >= 0
    assert c.shortfall_minutes == max(0, c.remaining_minutes - c.capacity_minutes)
    assert c.shortfall_minutes <= c.remaining_minutes
    assert (
        c.capacity_minutes <= params.daily_minutes * c.learn_days
    )  # never more than every minute of every reading day


@SETTINGS
@given(plans(min_days=1), st.integers(0, 60))
def test_capacity_never_grows_as_days_pass_and_never_shrinks_with_more_daily_time(plan, days_later):
    params, _, _ = plan
    params = cap.freeze_deadline(params)  # a stored deadline: the plan's own days only ever run out
    later = params.but(today=params.today + timedelta(days=days_later))
    assert cap.reading_capacity(later) <= cap.reading_capacity(params)
    more = params.but(daily_minutes=min(pc.DAILY_MINUTES_MAX, params.daily_minutes + 30))
    assert cap.reading_capacity(more) >= cap.reading_capacity(params)


@SETTINGS
@given(plans(min_days=1), st.integers(0, 60))
def test_a_frozen_deadline_never_slides_and_a_student_who_keeps_pace_is_never_pushed_behind(plan, days_later):
    params, papers, chapters = plan
    params = cap.freeze_deadline(params)
    first = rp.build_plan(params, papers, chapters)
    later = params.but(today=min(params.today + timedelta(days=days_later), params.exam_date - timedelta(days=1)))
    # the student reads exactly what the capacity of the days that went by allowed, in reading order
    done = (
        cap.reading_capacity(params) - cap.reading_capacity(later)
        if later.today < first.capacity.reading_deadline
        else first.capacity.capacity_minutes
    )
    left = first.capacity.remaining_minutes - min(first.capacity.remaining_minutes, max(0, done))
    kept = rp.build_plan(later, papers, [cap.ChapterInput("rest", papers[0].subject_key, est_minutes=left)])
    assert kept.capacity.reading_deadline == first.capacity.reading_deadline
    if first.health.shortfall_minutes == 0 and later.today < first.capacity.reading_deadline:
        assert kept.health.health == "on_track"


@SETTINGS
@given(plans(min_days=1), st.integers(1, 90))
def test_a_later_exam_never_lowers_the_capacity(plan, extra_days):
    params, _, _ = plan
    assert cap.reading_capacity(
        params.but(exam_date=params.exam_date + timedelta(days=extra_days))
    ) >= cap.reading_capacity(params)


@SETTINGS
@given(plans(), st.integers(0, 100))
def test_reading_more_never_raises_the_remaining_work(plan, extra_read):
    _, _, chapters = plan
    more = [cap.ChapterInput(**{**ch.__dict__, "read_pct": min(100, ch.read_pct + extra_read)}) for ch in chapters]
    assert cap.remaining_minutes(more) <= cap.remaining_minutes(chapters)


@SETTINGS
@given(st.integers(0, 10**6), st.integers(0, 10**6))
def test_health_bands_are_ordered_by_the_shortfall_and_stable_at_the_boundaries(shortfall, capacity):
    order = {"on_track": 0, "slightly_behind": 1, "at_risk": 2}
    band = hl.classify(shortfall, capacity)
    assert (band == "on_track") == (shortfall == 0)
    assert order[hl.classify(shortfall + 1, capacity)] >= order[band]
    if shortfall > 0:
        assert (band == "slightly_behind") == (shortfall * 10 <= capacity)
    assert (
        hl.classify(shortfall, capacity + 1) in {"on_track", band}
        or order[hl.classify(shortfall, capacity + 1)] <= order[band]
    )


# ---- milestones -------------------------------------------------------------------------------------------------------------


@SETTINGS
@given(plans(min_days=1))
def test_milestones_are_monotonic_unique_sorted_and_honest(plan):
    params, papers, chapters = plan
    computed = rp.build_plan(params, papers, chapters)
    rows = computed.milestones
    c = computed.capacity
    assert len({m.identity for m in rows}) == len(rows)
    assert [m.sort_order for m in rows] == list(range(len(rows)))
    assert [(m.target_date, ms.KIND_RANK[m.kind]) for m in rows] == sorted(
        (m.target_date, ms.KIND_RANK[m.kind]) for m in rows
    )
    assert [m.kind for m in rows].count("exam_week") == 1
    by = {m.identity: m for m in rows}
    assert by[("exam_week", "")].target_date == c.revise_until
    for paper in papers:
        f, r, m = (by[(kind, paper.subject_key)] for kind in pc.PAPER_MILESTONE_KINDS)
        assert params.today <= f.target_date < r.target_date < m.target_date
        remaining = computed.remaining_by_paper.get(paper.subject_key, 0)
        assert f.remaining_minutes == remaining and r.remaining_minutes == m.remaining_minutes == 0
        assert (f.status == "done") == (remaining == 0)
        if remaining:
            assert (f.status == "at_risk") == (f.target_date >= c.reading_deadline)
        assert (r.status == "at_risk") == (r.target_date > c.revise_until)
        assert (m.status == "at_risk") == (m.target_date > c.revise_until)
        assert r.target_date == f.target_date + timedelta(days=pc.FIRST_REVISION_GAP_DAYS)


@SETTINGS
@given(plans(min_days=1))
def test_within_a_lane_papers_finish_in_reading_order(plan):
    params, papers, chapters = plan
    by_paper = cap.remaining_by_paper(chapters)
    placements = ms.assign_lanes(papers, by_paper, params.lanes)
    finish = {
        m.subject_key: m.target_date
        for m in ms.build_milestones(params, papers, by_paper)
        if m.kind == "finish_reading"
    }
    for lane in range(params.lanes):
        dates = [
            finish[p.subject_key] for p in placements if p.lane == lane and by_paper.get(p.subject_key, 0) > 0
        ]  # a paper already read is done today, whatever its place
        assert dates == sorted(dates)
    loads = [0] * params.lanes
    for placement in placements:  # greedy: the lane chosen was the least loaded one at that moment
        assert loads[placement.lane] == min(loads)
        loads[placement.lane] = placement.lane_minutes


@SETTINGS
@given(plans(min_days=1))
def test_a_paper_finishes_before_the_deadline_exactly_when_its_lane_load_fits_the_capacity(plan):
    """Health (aggregate capacity) and milestones (lanes) agree: lane minutes x lanes <= capacity <=> finished by the deadline."""
    params, papers, chapters = plan
    computed = rp.build_plan(params, papers, chapters)
    placements = {p.subject_key: p for p in ms.assign_lanes(papers, computed.remaining_by_paper, params.lanes)}
    for row in computed.milestones:
        if row.kind != "finish_reading" or row.remaining_minutes == 0:
            continue
        fits = placements[row.subject_key].lane_minutes * params.lanes <= computed.capacity.capacity_minutes
        assert fits == (row.target_date < computed.capacity.reading_deadline)


@SETTINGS
@given(plans(min_days=1))
def test_a_plan_whose_total_work_fits_one_lane_share_is_never_reported_short(plan):
    params, papers, chapters = plan
    computed = rp.build_plan(params, papers, chapters)
    if computed.health.health == "on_track":
        assert computed.capacity.remaining_minutes <= computed.capacity.capacity_minutes
    if computed.capacity.remaining_minutes == 0:
        assert computed.health.health == "on_track"


@SETTINGS
@given(plans())
def test_the_plan_is_deterministic(plan):
    params, papers, chapters = plan
    assert rp.build_plan(params, papers, chapters) == rp.build_plan(params, list(reversed(papers)), list(chapters))


# ---- re-plan and options ----------------------------------------------------------------------------------------------------


@SETTINGS
@given(plans(min_days=1), st.integers(0, 40))
def test_replan_is_idempotent_and_applying_the_same_inputs_moves_nothing(plan, days_later):
    params, papers, chapters = plan
    stored = rp.build_plan(params, papers, chapters).milestones
    assert rp.replan(stored, params, papers, chapters).moved == ()
    later = params.but(today=params.today + timedelta(days=days_later))
    first = rp.replan(stored, later, papers, chapters)
    again = rp.replan(first.plan.milestones, later, papers, chapters)
    assert again.moved == () and again.added == () and again.plan.milestones == first.plan.milestones
    assert first.orphaned == () or later.exam_date <= later.today


@SETTINGS
@given(plans(min_days=1), st.integers(1, 40))
def test_letting_days_pass_never_moves_a_date_earlier_when_nothing_was_read(plan, days_later):
    params, papers, chapters = plan
    stored = rp.build_plan(params, papers, chapters).milestones
    later = params.but(today=min(params.today + timedelta(days=days_later), params.exam_date - timedelta(days=1)))
    for moved in rp.replan(stored, later, papers, chapters).moved:
        assert moved.kind != "finish_reading" or moved.days >= 0


@SETTINGS
@given(plans(min_days=1), st.sampled_from([None, 30, 120, 300]))
def test_options_exist_exactly_when_there_is_a_shortfall_and_a_feasible_one_closes_the_gap(plan, next_gap):
    params, papers, chapters = plan
    next_date = None if next_gap is None else params.exam_date + timedelta(days=next_gap)
    options = op.compute_options(params, chapters, next_date)
    short = cap.compute_capacity(params, chapters).shortfall_minutes
    assert bool(options) == (short > 0)
    assert [o["option"] for o in options] == [k for k in pc.OPTIONS if k != "more_time" or cap.learn_days(params) > 0][
        : len(options)
    ]
    for option in options:
        if not option["feasible"]:
            continue
        new_params, new_chapters = op.apply_option(params, chapters, option)
        assert cap.compute_capacity(new_params, new_chapters).shortfall_minutes == 0, option
    # choosing nothing changes nothing
    assert op.apply_option(params, chapters, {"option": "none"}) == (params, list(chapters))


@SETTINGS
@given(plans(min_days=1), st.integers(0, 500))
def test_skimming_saves_the_lowest_weight_first_and_stops_as_soon_as_it_is_enough(plan, shortfall):
    _, _, chapters = plan
    candidates = op.skim_candidates(chapters)
    assert [row[0] for row in candidates] == sorted(row[0] for row in candidates)
    picked, saved = op.skim_pick(chapters, shortfall)
    assert saved >= shortfall or len(picked) == len(candidates)
    if picked:
        assert saved - dict((k, s) for _, k, s in candidates)[picked[-1]] < shortfall  # the last chapter was needed


@SETTINGS
@given(plans(min_days=1), st.integers(0, 60), st.integers(0, 10))
def test_the_summary_always_fits_the_database_check(plan, days_later, gap):
    params, papers, chapters = plan
    stored = rp.build_plan(params, papers, chapters).milestones
    later = params.but(today=params.today + timedelta(days=days_later))
    result = rp.replan(stored, later, papers, chapters, next_exam_date=params.exam_date + timedelta(days=30 * gap))
    summary = rp.summary_json(result)
    assert len(json.dumps(summary)) <= pc.SUMMARY_MAX_CHARS and summary["v"] == pc.PLANNER_VERSION


@SETTINGS
@given(
    st.dates(min_value=date(2026, 1, 1), max_value=date(2027, 12, 31)),
    st.integers(0, 14),
    st.one_of(st.none(), st.integers(0, 10)),
)
def test_automatic_triggers_never_fire_inside_the_minimum_gap(today, missed, gap_days):
    last = None if gap_days is None else today - timedelta(days=gap_days)
    trigger = rp.should_replan(today=today, missed_days=missed, last_replanned_on=last)
    if trigger is not None:
        assert trigger in pc.AUTOMATIC_TRIGGERS and (last is None or gap_days >= pc.REPLAN_MIN_GAP_DAYS)
        assert (trigger == "missed_days") == (missed >= pc.REPLAN_MISSED_DAYS)
    elif last is None or gap_days >= pc.REPLAN_MIN_GAP_DAYS:
        assert missed < pc.REPLAN_MISSED_DAYS and today.weekday() != pc.REPLAN_WEEKDAY
