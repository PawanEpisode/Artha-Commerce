"""
Pure DTOs and types for F-11 Paper Analysis and Recommendation Engine.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID


@dataclass(frozen=True)
class AllocationIn:
    chapter_id: UUID
    marks: Decimal
    topic_id: UUID | None = None
    status: str = "confirmed"
    origin: str = "editor"
    rationale: str = ""


@dataclass(frozen=True)
class ChoiceGroupView:
    label: str
    pick_n: int
    of_m: int
    note: str = ""


@dataclass(frozen=True)
class PaperItem:
    label: str
    position: int
    question_id: UUID | None
    version_id: UUID | None
    marks: Decimal
    section_label: str
    choice_group_label: str | None
    format: str
    nature: str | None
    source_ref: str = ""


@dataclass(frozen=True)
class PaperView:
    title: str
    subject_key: str
    scheme_code: str
    term_code: str
    paper_kind: str
    series: str
    total_marks: Decimal
    duration_minutes: int | None
    source_url: str | None
    choice_groups: list[ChoiceGroupView]
    items: list[PaperItem]


@dataclass(frozen=True)
class PaperRef:
    id: UUID
    title: str
    term_code: str
    paper_kind: str
    subject_key: str = ""


@dataclass(frozen=True)
class SubjectStatus:
    subject_key: str
    data_status: str
    papers_published: int
    papers_target: int
    days_left: int | None
    seo_indexable: bool = False
    withheld_reason: str | None = None


@dataclass(frozen=True)
class ChapterStatsRow:
    chapter_id: UUID
    chapter_key: str
    name: str
    section: str
    papers_considered: int
    asked_n: int
    avg_effective: Decimal
    avg_when_asked: Decimal | None
    max_effective: Decimal | None
    last_asked_term_code: str | None
    share_of_marks: Decimal | None
    trend: Decimal | None
    comparability: str
    carried_papers: int
    weight_basis: str
    by_term: list[dict[str, Any]] = field(default_factory=list)


@dataclass(frozen=True)
class ChapterStatsView:
    subject_key: str
    scheme_id: UUID
    window: int
    include_practice: bool
    include_older: bool
    stats_version: int
    data_status: str
    chapters: list[ChapterStatsRow]


@dataclass(frozen=True)
class SittingPattern:
    term_code: str
    paper_kind: str
    total_marks: Decimal
    marks_objective: Decimal
    marks_descriptive: Decimal
    marks_theory: Decimal
    marks_practical: Decimal
    marks_optional_offered: Decimal
    marks_attemptable: Decimal
    choice_groups: list[dict[str, Any]]


@dataclass(frozen=True)
class PatternView:
    subject_key: str
    sittings: list[SittingPattern]


@dataclass(frozen=True)
class ChapterHistorySitting:
    term_code: str
    paper_kind: str
    marks_effective: Decimal
    marks_offered: Decimal
    questions: list[dict[str, Any]]


@dataclass(frozen=True)
class ChapterHistory:
    chapter_id: UUID
    chapter_key: str
    name: str
    subject_key: str
    window: int
    total_asked: int
    avg_effective: Decimal
    max_effective: Decimal | None
    sittings: list[ChapterHistorySitting]


@dataclass(frozen=True)
class AskedSummary:
    scope: str  # "question" | "topic" | "chapter"
    asked_n: int
    window_n: int
    last_asked_term_code: str | None
    last_asked_year: int | None
    label_key: str
    label: str


@dataclass(frozen=True)
class InferredWeight:
    chapter_id: UUID
    weight: float
    basis: str


@dataclass(frozen=True)
class WeaknessSignal:
    answered: int
    correct: float
    source: str
    updated_at: datetime | None = None


@dataclass(frozen=True)
class ReasonPayload:
    code: str
    params: dict[str, Any]
    sentence: str


@dataclass(frozen=True)
class ScoredChapter:
    chapter_id: UUID
    chapter_key: str
    name: str
    rank: int
    score: float
    tier: str  # "core" | "next" | "rest"
    confidence: str  # "high" | "medium" | "low" | "insufficient"
    components: dict[str, float]  # H, F, T, W, G
    expected_marks: float
    weight_basis: str
    comparability: str
    history: dict[str, Any]
    student: dict[str, Any]
    reasons: list[ReasonPayload]
    caveats: list[str]
    links: dict[str, str]


@dataclass(frozen=True)
class SubjectPriority:
    subject_key: str
    data_status: str
    ranking: str  # "available" | "withheld" | "unavailable"
    papers_considered: int
    sources: dict[str, int]
    confidence: str
    core_share_of_marks: float
    tiers: dict[str, int]
    chapters: list[ScoredChapter]
    ranking_reason: str | None = None


@dataclass(frozen=True)
class PriorityView:
    v: int
    snapshot_id: str
    engine_version: str
    weightset_id: str
    template_version: int
    generated_at: str
    days_left: int | None
    exam_date_source: str
    disclaimer_key: str
    subjects: list[SubjectPriority]


@dataclass(frozen=True)
class PlanInputs:
    days: int
    hours_per_day: float
    subject_keys: Sequence[str]
    balance_subjects: bool = False


@dataclass(frozen=True)
class PlanPreviewItem:
    chapter_id: UUID
    chapter_key: str
    subject_key: str
    minutes: int
    mode: str  # "full" | "key_points"
    expected_gain: float
    mph: float
    effort_basis: str


@dataclass(frozen=True)
class PlanPreview:
    v: int
    inputs: dict[str, Any]
    budget_hours: float
    hours_used: float
    items: list[PlanPreviewItem]
    covered_share: float
    left_out: dict[str, Any]
    snapshot_id: str | None
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class PlanItemView:
    id: UUID
    chapter_id: UUID
    chapter_key: str
    subject_key: str
    planned_date: date
    position: int
    minutes: int
    mode: str
    expected_gain: Decimal
    mph: Decimal
    state: str


@dataclass(frozen=True)
class PlanView:
    id: UUID
    user_id: UUID
    client_id: UUID
    status: str
    days: int
    hours_per_day: Decimal
    tz: str
    start_date: date
    end_date: date
    subject_keys: list[str]
    balance_subjects: bool
    summary: dict[str, Any]
    items: list[PlanItemView]
