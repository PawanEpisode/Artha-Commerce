"""
Building and re-planning (FR-F13-47, FR-F13-49).

`build_plan` is the whole computation: capacity, health and milestones from the student's inputs and chapters. A re-plan is the
same computation from today's progress, compared with the stored milestones:

- a milestone that is done or dropped is never touched; a `finish_reading` that has just become done (nothing left to read) is
  reported in `completed`, not as moved, and the first revision of that paper follows the day it finished;
- a milestone that disappears from the new computation is reported (`orphaned`), never deleted: content is not dropped silently;
- when nothing is short (`auto_apply`), the new dates apply and `moved` lists what changed;
- when there is a shortfall, the new dates and the options are only a proposal: nothing applies until the student chooses.

Re-planning twice with the same inputs moves nothing the second time.
"""

from __future__ import annotations

import json
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import date, timedelta
from typing import Any

from . import capacity as cap
from . import constants as pc
from . import health as hl
from . import milestones as ms
from . import options as op

FROZEN_STATUSES = ("done", "dropped")


@dataclass(frozen=True)
class PlanComputation:
    params: cap.PlanParams
    capacity: cap.Capacity
    health: hl.Health
    milestones: tuple[ms.MilestoneRow, ...]
    remaining_by_paper: dict[str, int]


def build_plan(
    params: cap.PlanParams,
    papers: Sequence[cap.PaperInput],
    chapters: Sequence[cap.ChapterInput],
    finished_on: Mapping[str, date] | None = None,
) -> PlanComputation:
    """Capacity, health and milestones for a plan. After the exam day: health `unknown` and no milestones.

    `finished_on` maps a paper to the date its reading was marked done (see `ms.build_milestones`); a new plan has none.
    """
    capacity = cap.compute_capacity(params, chapters)
    by_paper = cap.remaining_by_paper(chapters)
    health = hl.assess(
        remaining_minutes=capacity.remaining_minutes,
        capacity_minutes=capacity.capacity_minutes,
        plan_over=capacity.runway_days == 0,
    )
    return PlanComputation(
        params, capacity, health, tuple(ms.build_milestones(params, papers, by_paper, finished_on)), by_paper
    )


# ---- when to re-plan --------------------------------------------------------------------------------------------------------


def consecutive_missed_days(active_days: Collection[date], today: date, since: date) -> int:
    """Local days before today with no activity, counted back from yesterday until a day with activity (or `since`, the plan's start)."""
    missed = 0
    day = today - timedelta(days=1)
    while day >= since and day not in active_days:
        missed += 1
        day -= timedelta(days=1)
    return missed


def should_replan(
    *,
    today: date,
    missed_days: int,
    last_replanned_on: date | None,
    manual: bool = False,
    exam_date_changed: bool = False,
    scheme_switched: bool = False,
) -> str | None:
    """The trigger that applies today, or None. A student's request, a new exam date and a scheme switch always re-plan; the two
    automatic triggers (2 missed days, every Monday) wait until the last re-plan is at least 3 days old, so a long break does not
    re-plan every day."""
    if manual:
        return "manual"
    if exam_date_changed:
        return "exam_date"
    if scheme_switched:
        return "scheme_switch"
    if last_replanned_on is not None and (today - last_replanned_on).days < pc.REPLAN_MIN_GAP_DAYS:
        return None
    if missed_days >= pc.REPLAN_MISSED_DAYS:
        return "missed_days"
    if today.weekday() == pc.REPLAN_WEEKDAY:
        return "weekly"
    return None


# ---- the re-plan ------------------------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Moved:
    subject_key: str
    kind: str
    from_date: date
    to_date: date

    @property
    def days(self) -> int:
        """Positive when the milestone moved later."""
        return (self.to_date - self.from_date).days


@dataclass(frozen=True)
class ReplanResult:
    plan: PlanComputation  # the new computation (with the merged milestones)
    health_before: str
    health_after: str
    shortfall_before: int
    shortfall_after: int
    moved: tuple[Moved, ...]
    completed: tuple[
        ms.MilestoneRow, ...
    ]  # reading finished since the last check: now `done`, dated the day it was noticed
    added: tuple[ms.MilestoneRow, ...]  # in the new computation, not stored yet
    orphaned: tuple[
        ms.MilestoneRow, ...
    ]  # stored, no longer computed (a paper left the plan): the service decides, nothing is dropped here
    options: tuple[dict[str, Any], ...]
    auto_apply: bool  # no shortfall: the dates apply now. Otherwise everything is a proposal until the student chooses

    @property
    def moved_count(self) -> int:
        return len(self.moved)


def replan(
    previous: Sequence[ms.MilestoneRow],
    params: cap.PlanParams,
    papers: Sequence[cap.PaperInput],
    chapters: Sequence[cap.ChapterInput],
    *,
    health_before: str = "unknown",
    shortfall_before: int = 0,
    next_exam_date: date | None = None,
) -> ReplanResult:
    old = {row.identity: row for row in previous}
    finished_on = {
        row.subject_key: row.target_date for row in previous if row.kind == "finish_reading" and row.status == "done"
    }
    computed = build_plan(params, papers, chapters, finished_on)
    fresh = {row.identity: row for row in computed.milestones}

    merged: list[ms.MilestoneRow] = []
    moved: list[Moved] = []
    added: list[ms.MilestoneRow] = []
    completed: list[ms.MilestoneRow] = []
    for identity, row in fresh.items():
        before = old.get(identity)
        if before is None:
            added.append(row)
            merged.append(row)
        elif before.status in FROZEN_STATUSES:
            merged.append(replace(before, sort_order=row.sort_order))
        elif row.status == "done":
            # Nothing left to read: the milestone is achieved (today, as far as the planner can tell: services mark it done when
            # the last chapter is read, so the date is right). It is reported as completed, not as moved.
            completed.append(row)
            merged.append(row)
        else:
            if before.target_date != row.target_date:
                moved.append(Moved(row.subject_key, row.kind, before.target_date, row.target_date))
            merged.append(row)
    orphaned = tuple(row for identity, row in old.items() if identity not in fresh)

    merged.sort(key=lambda r: (r.target_date, ms.KIND_RANK[r.kind], r.sort_order))
    merged = [
        ms.MilestoneRow(r.subject_key, r.kind, r.target_date, r.remaining_minutes, r.status, i)
        for i, r in enumerate(merged)
    ]
    plan = PlanComputation(
        computed.params, computed.capacity, computed.health, tuple(merged), computed.remaining_by_paper
    )

    plan_over = computed.capacity.runway_days == 0
    options = () if plan_over else tuple(op.compute_options(params, chapters, next_exam_date))
    return ReplanResult(
        plan=plan,
        health_before=health_before,
        health_after=computed.health.health,
        shortfall_before=shortfall_before,
        shortfall_after=computed.health.shortfall_minutes,
        moved=tuple(moved),
        completed=tuple(completed),
        added=tuple(added),
        orphaned=orphaned,
        options=options,
        auto_apply=not plan_over and computed.health.shortfall_minutes == 0,
    )


def summary_json(result: ReplanResult) -> dict[str, Any]:
    """The `today_replanevent.summary` payload (ERD 2.8): `{"v": 1, "moved": [...], "options": [...]}`, at most 8 KB.

    If it is too big the skim chapter lists go first, then the moved list is cut from the end.
    """
    moved = [
        {"subject_key": m.subject_key, "kind": m.kind, "from": m.from_date.isoformat(), "to": m.to_date.isoformat()}
        for m in result.moved[: pc.SUMMARY_MAX_MOVED]
    ]
    options = [dict(option) for option in result.options]
    payload: dict[str, Any] = {"v": pc.PLANNER_VERSION, "moved": moved, "options": options}

    def size() -> int:
        return len(json.dumps(payload))  # PostgreSQL renders jsonb with ", " and ": ", which is what the CHECK counts

    if size() > pc.SUMMARY_MAX_CHARS:
        for option in options:
            option.pop("chapters", None)
    while size() > pc.SUMMARY_MAX_CHARS and moved:
        moved.pop()
    return payload
