"""
Milestones per paper (FR-F13-47): finish reading, first revision and a mock, plus one `exam_week` milestone for the plan.

Papers are sorted by (marks desc, paper number) and handed to the reading lanes greedily: each paper goes to the lane with the
least work so far, so the lanes stay balanced and the last `finish_reading` agrees with the plan's health whenever the papers are
small next to the whole. A lane reads at `daily x utilisation x learn share / lanes` minutes a day.

Dates are honest: when the work does not fit, `finish_reading` and `first_revision` run past their windows and the milestone is
marked `at_risk`, never clamped. Reading must end before the deadline (the deadline is the first day without reading), so a finish
on or after it is `at_risk`; a first revision or mock may fall on the first day of exam week at the latest. For every paper the dates stay strictly in order: finish < first revision < mock.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, timedelta

from . import capacity as cap
from . import constants as pc

KIND_RANK = {"finish_reading": 0, "first_revision": 1, "mock": 2, "exam_week": 3}
NO_PAPER_NUMBER = 10_000  # a paper without a number sorts after the numbered ones


@dataclass(frozen=True)
class MilestoneRow:
    """One milestone as the planner computes it (the services turn it into a `today_milestone` row)."""

    subject_key: str  # empty for `exam_week`
    kind: str
    target_date: date
    remaining_minutes: int
    status: str
    sort_order: int

    @property
    def identity(self) -> tuple[str, str]:
        """The unique key of a milestone inside a plan: `(kind, subject_key)`."""
        return (self.kind, self.subject_key)


@dataclass(frozen=True)
class LanePlacement:
    subject_key: str
    lane: int  # 0-based
    lane_minutes: int  # the lane's reading minutes up to and including this paper


def reading_order(papers: list[cap.PaperInput] | tuple[cap.PaperInput, ...]) -> list[cap.PaperInput]:
    """Marks descending, then paper number, then key (so the order is total and stable)."""
    return sorted(
        papers,
        key=lambda p: (
            -(p.marks or 0),
            p.paper_number if p.paper_number is not None else NO_PAPER_NUMBER,
            p.subject_key,
        ),
    )


def assign_lanes(
    papers: list[cap.PaperInput] | tuple[cap.PaperInput, ...], remaining: dict[str, int], lanes: int
) -> list[LanePlacement]:
    """Greedy least-loaded lane per paper, in reading order (the first lane wins a tie). A paper with nothing left adds no load."""
    loads = [0] * lanes
    placements: list[LanePlacement] = []
    for paper in reading_order(papers):
        work = max(0, remaining.get(paper.subject_key, 0))
        lane = loads.index(min(loads))
        loads[lane] += work
        placements.append(LanePlacement(paper.subject_key, lane, loads[lane]))
    return placements


def finish_date(params: cap.PlanParams, lane_minutes: int) -> date:
    """The last study day of the work in a lane: `ceil(minutes x lanes / per-day rate)` days from today, today being day one."""
    if lane_minutes <= 0:
        return params.today
    days = cap.ceil_div(lane_minutes * params.lanes * cap.PERCENT_PAIR, params.daily_rate)
    return params.today + timedelta(days=days - 1)


def build_milestones(
    params: cap.PlanParams,
    papers: list[cap.PaperInput] | tuple[cap.PaperInput, ...],
    remaining: dict[str, int],
    finished_on: Mapping[str, date] | None = None,
) -> list[MilestoneRow]:
    """All milestones of a plan, sorted by date. Empty once the exam day has come (there is nothing left to plan).

    A paper with nothing left to read finished on `finished_on[subject_key]` (the date its `finish_reading` was marked done) or,
    when that is not known, today. Its first revision follows that date, so it does not slide later as the days pass.
    """
    finished_on = finished_on or {}
    deadline = cap.reading_deadline(params)
    exam_week_start = cap.revise_until(params)
    if deadline is None or exam_week_start is None:
        return []

    order = {p.subject_key: index for index, p in enumerate(reading_order(papers))}
    drafts: list[tuple[date, int, int, MilestoneRow]] = []

    for placement in assign_lanes(papers, remaining, params.lanes):
        key = placement.subject_key
        work = max(0, remaining.get(key, 0))
        finish = finish_date(params, placement.lane_minutes) if work else finished_on.get(key, params.today)
        first_revision = finish + timedelta(days=pc.FIRST_REVISION_GAP_DAYS)
        mock = max(deadline + timedelta(days=pc.MOCK_GAP_DAYS), first_revision + timedelta(days=1))
        rows = (
            MilestoneRow(
                key,
                "finish_reading",
                finish,
                work,
                "done" if not work else ("at_risk" if finish >= deadline else "pending"),
                0,
            ),
            MilestoneRow(
                key,
                "first_revision",
                first_revision,
                0,
                "at_risk" if first_revision > exam_week_start else "pending",
                0,
            ),
            MilestoneRow(key, "mock", mock, 0, "at_risk" if mock > exam_week_start else "pending", 0),
        )
        for row in rows:
            drafts.append((row.target_date, KIND_RANK[row.kind], order[key], row))

    drafts.append(
        (exam_week_start, KIND_RANK["exam_week"], 0, MilestoneRow("", "exam_week", exam_week_start, 0, "pending", 0))
    )
    drafts.sort(key=lambda item: item[:3])
    return [
        MilestoneRow(r.subject_key, r.kind, r.target_date, r.remaining_minutes, r.status, index)
        for index, (_, _, _, r) in enumerate(drafts)
    ]
