"""
Capacity: how many reading minutes the days before the reading deadline can hold, how many are left to read, and the gap
(ERD "Planner", FR-F13-47, FR-F13-48).

All arithmetic is integer percent maths with floors on capacity and ceilings on work, so a result is exact and a golden fixture
can be checked by hand. "Today" counts as a full study day. Nothing here reads a clock: `today` is always an argument (the
student's local date).
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, timedelta

from . import constants as pc

PERCENT_PAIR = 10_000  # utilisation percent x learn-share percent


def ceil_div(numerator: int, denominator: int) -> int:
    """Ceiling of a division of non-negative integers (denominator above zero)."""
    return -(-numerator // denominator)


def half_up_pct(value: int, pct: int) -> int:
    """`round(value * pct / 100)` with halves rounded up (Python's `round` rounds halves to even, which surprises in a spec)."""
    return (value * pct + 50) // 100


@dataclass(frozen=True)
class ChapterInput:
    """One chapter as the planner needs it. `read_pct` is the student's coverage (0 to 100); an excluded chapter is not planned."""

    key: str
    subject_key: str
    est_minutes: int | None = None
    read_pct: int = 0
    marks_weight: float = 1.0
    excluded: bool = False
    skim: bool = False  # the student chose "skim low-weight chapters": the work left in it counts half


@dataclass(frozen=True)
class PaperInput:
    """One paper (a syllabus subject). `marks` is the paper's total marks; both fields only decide the reading order."""

    subject_key: str
    paper_number: int | None = None
    marks: int | None = None


@dataclass(frozen=True)
class PlanParams:
    """The student's inputs to a plan (the columns of `today_studyplan`). Invalid values raise `ValueError`."""

    today: date
    exam_date: date
    daily_minutes: int
    utilisation_pct: int = pc.UTILISATION_PCT_DEFAULT
    learn_share_pct: int = pc.LEARN_SHARE_PCT_DEFAULT
    lanes: int = pc.LANES_DEFAULT
    exam_week_days: int = pc.EXAM_WEEK_DAYS_DEFAULT
    # The reading deadline the plan was created with (`today_studyplan.reading_deadline`). None means "work it out from the runway
    # as of `today`", which is what a new plan does. A re-plan passes the stored one: the formula moves later as the runway
    # shrinks, so recomputing it would slide every mock later for a student who never misses a day.
    reading_deadline: date | None = None

    def __post_init__(self) -> None:
        if self.reading_deadline is not None and self.reading_deadline > self.exam_date:
            raise ValueError("reading_deadline cannot be after the exam date")
        checks = (
            ("daily_minutes", self.daily_minutes, pc.DAILY_MINUTES_MIN, pc.DAILY_MINUTES_MAX),
            ("utilisation_pct", self.utilisation_pct, pc.UTILISATION_PCT_MIN, pc.UTILISATION_PCT_MAX),
            ("learn_share_pct", self.learn_share_pct, pc.LEARN_SHARE_PCT_MIN, pc.LEARN_SHARE_PCT_MAX),
            ("lanes", self.lanes, 1, pc.LANES_MAX),
            ("exam_week_days", self.exam_week_days, 0, pc.EXAM_WEEK_DAYS_MAX),
        )
        for name, value, low, high in checks:
            if not low <= value <= high:
                raise ValueError(f"{name} must be between {low} and {high}, got {value}")

    def but(self, **changes) -> PlanParams:
        return replace(self, **changes)

    @property
    def daily_rate(self) -> int:
        """Reading minutes a day, times 10 000 (so it stays an integer): `daily x utilisation x learn share`."""
        return self.daily_minutes * self.utilisation_pct * self.learn_share_pct


@dataclass(frozen=True)
class Capacity:
    runway_days: int  # study days from today up to the day before the exam
    reading_deadline: date | None  # None once the exam day has come
    revise_until: date | None  # the start of exam week: the revise window ends here
    learn_days: int  # study days from today up to the day before the reading deadline (0 when it has passed)
    capacity_minutes: int
    remaining_minutes: int
    shortfall_minutes: int


def runway_days(today: date, exam_date: date) -> int:
    """Study days from today to the day before the exam, today included. 0 on the exam day and after it."""
    return max(0, (exam_date - today).days)


def reading_buffer_days(runway: int) -> int:
    """`max(14, round(30% of the runway))`: the reading ends this many days before the exam."""
    return max(pc.READING_BUFFER_MIN_DAYS, half_up_pct(runway, pc.READING_BUFFER_PCT))


def formula_deadline(params: PlanParams) -> date | None:
    """The deadline the ERD formula gives as of `today`: `exam - max(14, 30% of the runway)`. None once the exam day has come."""
    runway = runway_days(params.today, params.exam_date)
    if runway == 0:
        return None
    return params.exam_date - timedelta(days=reading_buffer_days(runway))


def reading_deadline(params: PlanParams) -> date | None:
    """The plan's reading deadline: the stored one when the plan has one, otherwise the formula. None once the exam day has come.

    The deadline is the first day with no reading: reading days are the days from today up to the day before it.
    """
    if runway_days(params.today, params.exam_date) == 0:
        return None
    return params.reading_deadline or formula_deadline(params)


def freeze_deadline(params: PlanParams) -> PlanParams:
    """The same inputs with the deadline fixed as of today: what a new plan stores, and what a re-plan then passes back in."""
    return params.but(reading_deadline=formula_deadline(params))


def revise_until(params: PlanParams) -> date | None:
    if runway_days(params.today, params.exam_date) == 0:
        return None
    return params.exam_date - timedelta(days=params.exam_week_days)


def learn_days(params: PlanParams) -> int:
    deadline = reading_deadline(params)
    if deadline is None:
        return 0
    return max(0, (deadline - params.today).days)


def reading_capacity(params: PlanParams) -> int:
    """Reading minutes the learn window holds: `learn days x daily x utilisation x learn share`, floored once at the end."""
    return learn_days(params) * params.daily_rate // PERCENT_PAIR


def chapter_remaining(chapter: ChapterInput) -> int:
    """Minutes still to read: the estimate (60 when missing) times the unread share, rounded up. Excluded chapters count 0."""
    if chapter.excluded:
        return 0
    estimate = pc.DEFAULT_CHAPTER_MINUTES if chapter.est_minutes is None else max(0, chapter.est_minutes)
    unread = 100 - min(100, max(0, chapter.read_pct))
    left = ceil_div(estimate * unread, 100)
    return ceil_div(left * pc.SKIM_FACTOR_PCT, 100) if chapter.skim else left


def remaining_minutes(chapters: list[ChapterInput] | tuple[ChapterInput, ...]) -> int:
    return sum(chapter_remaining(ch) for ch in chapters)


def remaining_by_paper(chapters: list[ChapterInput] | tuple[ChapterInput, ...]) -> dict[str, int]:
    """Minutes left per `subject_key`. A paper whose chapters are all read or excluded appears with 0."""
    totals: dict[str, int] = {}
    for chapter in chapters:
        totals[chapter.subject_key] = totals.get(chapter.subject_key, 0) + chapter_remaining(chapter)
    return totals


def compute_capacity(params: PlanParams, chapters: list[ChapterInput] | tuple[ChapterInput, ...]) -> Capacity:
    capacity = reading_capacity(params)
    remaining = remaining_minutes(chapters)
    return Capacity(
        runway_days=runway_days(params.today, params.exam_date),
        reading_deadline=reading_deadline(params),
        revise_until=revise_until(params),
        learn_days=learn_days(params),
        capacity_minutes=capacity,
        remaining_minutes=remaining,
        shortfall_minutes=max(0, remaining - capacity),
    )
