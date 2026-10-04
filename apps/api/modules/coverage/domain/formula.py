"""
The coverage maths as pure functions (no Django, no I/O). Mirrored in TypeScript for optimistic UI and tested
against the shared fixtures in `tests/fixtures/formula_cases.json`. ERD section 4.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

STATUS_NOT_STARTED = "not_started"
STATUS_READING = "reading"
STATUS_PRACTISED = "practised"
STATUS_REVISED_ONCE = "revised_once"
STATUS_REVISED_TWICE_PLUS = "revised_twice_plus"
STATUS_EXAM_READY = "exam_ready"

EXAM_READY_COVERAGE = 85
EXAM_READY_REVISIONS = 2


def round_half_up(value: float) -> int:
    """Percentages round half up (Python's round() is banker's rounding)."""
    return int(value + 0.5)


@dataclass(frozen=True)
class Weights:
    read: int = 40
    practice: int = 30
    revise: int = 20
    mock: int = 10

    @property
    def total(self) -> int:
        return self.read + self.practice + self.revise + self.mock


@dataclass(frozen=True)
class ChapterInputs:
    topics_total: int
    topics_done: int
    practice_count: int
    revision_count: int
    mock_count: int
    target_practice_sets: int = 1
    target_revisions: int = 2
    target_mocks: int = 1


@dataclass(frozen=True)
class Components:
    read: int
    practice: int
    revise: int
    mock: int
    coverage: int


def _component(count: int, target: int) -> int:
    return round_half_up(100 * min(1.0, count / target))


_DEFAULT_WEIGHTS = Weights()


def compute_components(inputs: ChapterInputs, weights: Weights = _DEFAULT_WEIGHTS) -> Components:
    """
    read     = 100 * done / total          (a chapter without topics passes total = 1, done = 0 or 1)
    practice = 100 * min(1, count / target)
    revise   = 100 * min(1, count / target)
    mock     = 100 * min(1, count / target)
    coverage = weighted by the student's weights. A component whose target is 0 is not applicable and its weight
    is redistributed proportionally across the others.
    """
    total = max(inputs.topics_total, 1)
    read = round_half_up(100 * min(inputs.topics_done, total) / total)
    practice = _component(inputs.practice_count, inputs.target_practice_sets) if inputs.target_practice_sets else 0
    revise = _component(inputs.revision_count, inputs.target_revisions) if inputs.target_revisions else 0
    mock = _component(inputs.mock_count, inputs.target_mocks) if inputs.target_mocks else 0

    parts = [
        (read, weights.read),
        (practice, weights.practice if inputs.target_practice_sets else 0),
        (revise, weights.revise if inputs.target_revisions else 0),
        (mock, weights.mock if inputs.target_mocks else 0),
    ]
    weight_sum = sum(w for _, w in parts)
    coverage = read if weight_sum == 0 else round_half_up(sum(v * w for v, w in parts) / weight_sum)
    return Components(read=read, practice=practice, revise=revise, mock=mock, coverage=min(coverage, 100))


def derive_status(
    *, read_pct: int, coverage_pct: int, practice_count: int, revision_count: int, any_activity: bool
) -> str:
    """First match from the top (ERD section 4)."""
    if coverage_pct >= EXAM_READY_COVERAGE and revision_count >= EXAM_READY_REVISIONS:
        return STATUS_EXAM_READY
    if revision_count >= 2:
        return STATUS_REVISED_TWICE_PLUS
    if revision_count == 1:
        return STATUS_REVISED_ONCE
    if read_pct == 100 and practice_count >= 1:
        return STATUS_PRACTISED
    if read_pct > 0 or any_activity:
        return STATUS_READING
    return STATUS_NOT_STARTED


def marks_weight(marks_min: Decimal | float | None, marks_max: Decimal | float | None) -> float:
    """coalesce((min + max) / 2, max, min, 1)."""
    if marks_min is not None and marks_max is not None:
        return float(marks_min + marks_max) / 2
    if marks_max is not None:
        return float(marks_max)
    if marks_min is not None:
        return float(marks_min)
    return 1.0


@dataclass(frozen=True)
class RollupRow:
    coverage_pct: int
    weight: float
    is_excluded: bool
    status: str


@dataclass(frozen=True)
class RollupResult:
    pct_simple: int
    pct_weighted: int
    chapters_total: int
    chapters_done: int


def rollup(rows: list[RollupRow]) -> RollupResult:
    """Over chapters that are not excluded: simple average and marks-weighted average."""
    included = [r for r in rows if not r.is_excluded]
    if not included:
        return RollupResult(0, 0, 0, 0)
    simple = round_half_up(sum(r.coverage_pct for r in included) / len(included))
    weight_sum = sum(r.weight for r in included)
    weighted = round_half_up(sum(r.coverage_pct * r.weight for r in included) / weight_sum) if weight_sum else simple
    done = sum(1 for r in included if r.coverage_pct >= 100 or r.status == STATUS_EXAM_READY)
    return RollupResult(simple, weighted, len(included), done)


DEFAULT_REVISION_DAYS = (3, 7, 21, 45)


def next_revision_due(
    occurred_on: date, revision_count: int, revision_days: list[int] | tuple[int, ...]
) -> date | None:
    """
    After the Nth revision the next one is due `revision_days[N - 1]` days later; the last gap repeats.
    The first revision with the default schedule is due in 3 days.
    """
    if revision_count < 1 or not revision_days:
        return None
    gap = revision_days[min(revision_count, len(revision_days)) - 1]
    return occurred_on + timedelta(days=gap)


def weights_valid(weights: Weights) -> bool:
    values = (weights.read, weights.practice, weights.revise, weights.mock)
    return all(0 <= v <= 100 for v in values) and weights.total == 100


def revision_days_valid(days: object) -> bool:
    return (
        isinstance(days, list)
        and 1 <= len(days) <= 8
        and all(isinstance(d, int) and not isinstance(d, bool) and 1 <= d <= 365 for d in days)
    )
