"""A small day-by-day student for the planner simulation tests (a test helper, not a test).

The student reads in reading order at the plan's rate on the days the `activity` function says she studies, the way a service
would call the planner each morning: count missed days, ask `should_replan`, re-plan, and (when there is a shortfall) let a
policy pick one of the options. The planner is only ever called with the student's local date, as in production.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, timedelta
from fractions import Fraction

from modules.today.planner import capacity as cap
from modules.today.planner import milestones as ms
from modules.today.planner import options as op
from modules.today.planner import replan as rp

START = date(2026, 10, 15)  # a Thursday
EXAM = date(2027, 1, 14)
PAPERS = [cap.PaperInput(f"p{i}", i, 100) for i in (1, 2, 3, 4)]


@dataclass
class Event:
    day: date
    trigger: str
    health_before: str
    health_after: str
    shortfall_after: int
    auto_apply: bool
    moved: int
    options: list[str]
    chosen: str | None = None


@dataclass
class Sim:
    params: cap.PlanParams
    left: dict[str, Fraction]  # minutes left per chapter key (exact, so a day's reading is exactly the plan's rate)
    style: str = (
        "parallel"  # parallel: each lane reads its own papers (the plan's model); sequential: one paper after another
    )
    stored: tuple[ms.MilestoneRow, ...] = ()
    active: set[date] = field(default_factory=set)
    last_replanned_on: date | None = None
    events: list[Event] = field(default_factory=list)
    daily_health: list[tuple[date, str, int]] = field(default_factory=list)
    read_done_on: date | None = None
    stored_history: list[tuple[date, tuple[ms.MilestoneRow, ...]]] = field(default_factory=list)

    @classmethod
    def new(cls, share: float, daily: int = 180, exam: date = EXAM, style: str = "parallel") -> Sim:
        params = cap.freeze_deadline(cap.PlanParams(START, exam, daily))
        total = int(cap.reading_capacity(params) * Fraction(share).limit_denominator(100))
        per_chapter = total // 8
        left = {f"{p.subject_key}-{n}": Fraction(per_chapter) for p in PAPERS for n in (1, 2)}
        sim = cls(params, left, style=style)
        sim.stored = rp.build_plan(params, PAPERS, sim.chapters()).milestones
        return sim

    def chapters(self) -> list[cap.ChapterInput]:
        return [
            cap.ChapterInput(key, key.split("-")[0], est_minutes=math.ceil(minutes))
            for key, minutes in sorted(self.left.items())
        ]

    def remaining(self) -> Fraction:
        return sum(self.left.values(), Fraction(0))

    def _eat(self, keys: list[str], minutes: Fraction) -> Fraction:
        """Read `minutes` through the chapters in order; returns what could not be used (everything was read)."""
        for key in keys:
            used = min(minutes, self.left[key])
            self.left[key] -= used
            minutes -= used
            if not minutes:
                break
        return minutes

    def read(self, minutes: Fraction) -> None:
        keys = sorted(self.left)
        if self.style == "sequential":
            self._eat(keys, minutes)
            return
        by_paper = cap.remaining_by_paper(self.chapters())
        lanes = ms.assign_lanes(PAPERS, by_paper, self.params.lanes)
        spare = Fraction(0)
        for lane in range(self.params.lanes):
            mine = [p.subject_key for p in lanes if p.lane == lane]
            spare += self._eat([k for k in keys if k.split("-")[0] in mine], minutes / self.params.lanes)
        if spare:
            self._eat(keys, spare)  # a lane that ran dry helps the others

    def morning(
        self, today: date, *, choose: Callable[[list[dict]], dict | None] | None = None, next_exam: date | None = None
    ):
        params = self.params.but(today=today)
        before = rp.build_plan(params, PAPERS, self.chapters())
        missed = rp.consecutive_missed_days(self.active, today, START)
        trigger = rp.should_replan(today=today, missed_days=missed, last_replanned_on=self.last_replanned_on)
        if trigger:
            result = rp.replan(
                self.stored,
                params,
                PAPERS,
                self.chapters(),
                health_before=before.health.health,
                shortfall_before=before.health.shortfall_minutes,
                next_exam_date=next_exam,
            )
            event = Event(
                today,
                trigger,
                result.health_before,
                result.health_after,
                result.shortfall_after,
                result.auto_apply,
                result.moved_count,
                [o["option"] for o in result.options],
            )
            if result.auto_apply:
                self.stored = result.plan.milestones
            elif choose and (picked := choose(list(result.options))):
                self._apply(picked, today, params)
                event.chosen = picked["option"]
            self.last_replanned_on = today
            self.events.append(event)
        after = rp.build_plan(self.params.but(today=today), PAPERS, self.chapters())
        self.daily_health.append((today, after.health.health, after.health.shortfall_minutes))

    def _apply(self, option: dict, today: date, params: cap.PlanParams) -> None:
        new_params, new_chapters = op.apply_option(params, self.chapters(), option)
        self.params = new_params.but(today=START)
        for chapter in new_chapters:
            self.left[chapter.key] = cap.chapter_remaining(chapter)  # a skimmed chapter now has half the work
        result = rp.replan(self.stored, self.params.but(today=today), PAPERS, self.chapters())
        self.stored = result.plan.milestones
        self.params = (
            cap.freeze_deadline(self.params.but(today=today)) if option["option"] == "next_attempt" else self.params
        )

    def evening(self, today: date, fraction: float) -> None:
        if fraction > 0:
            self.active.add(today)
            self.read(Fraction(self.params.daily_rate, 10_000) * Fraction(fraction).limit_denominator(100))
        if self.remaining() == 0 and self.read_done_on is None:
            self.read_done_on = today

    def run(self, days: int, activity: Callable[[int], float], **kwargs) -> Sim:
        for d in range(days):
            today = START + timedelta(days=d)
            self.morning(today, **kwargs)
            self.stored_history.append((today, self.stored))
            self.evening(today, activity(d))
        return self
