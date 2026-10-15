"""
QuestionPayload schema ('artha.question.v1') definition (F-06 ERD 3.6).
Used for import, export, upsert_from_source, and the authoring editor API.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Literal, TypedDict


class OptionPayload(TypedDict, total=False):
    body_md: str
    is_correct: bool
    feedback_md: str
    pinned: bool


class NumericKeyPayload(TypedDict, total=False):
    numeric_value: Decimal | str | float
    tolerance_abs: Decimal | str | float
    tolerance_rel: Decimal | str | float
    accepted_values: list[Decimal | str | float]
    unit: str
    unit_required: bool
    key_note: str


class RubricStepPayload(TypedDict, total=False):
    title: str
    description_md: str
    marks: Decimal | str | float
    kind: str
    keywords: list[str]
    mandatory: bool
    partial_allowed: bool


class RubricPayload(TypedDict, total=False):
    reference_solution_md: str
    answer_template_md: str
    steps: list[RubricStepPayload]
    keywords: list[str]
    common_mistakes_md: str
    source: str


class LabelsPayload(TypedDict, total=False):
    source_kind: str
    source_name: str
    source_url: str
    source_ref: str
    source_year: int | None
    source_term_code: str
    difficulty: int | None
    bloom: str
    nature: str
    tags: list[str]


class MappingPayload(TypedDict, total=False):
    course: str
    level: str
    subject_key: str
    chapter_key: str
    topic_key: str | None
    primary: bool


class MediaPayload(TypedDict, total=False):
    ref: str
    alt: str
    url_or_attachment: str


class QuestionPayload(TypedDict, total=False):
    schema: Literal["artha.question.v1"]
    kind: str
    stem_md: str
    options: list[OptionPayload]
    numeric_key: NumericKeyPayload | None
    explanation_md: str
    explanation_source: str
    reference_labels: list[str]
    marks: Decimal | str | float
    negative_marks: Decimal | str | float | None
    multi_scoring: str
    rubric: RubricPayload | None
    children: list[QuestionPayload]
    labels: LabelsPayload
    mapping: list[MappingPayload]
    media: list[MediaPayload]
