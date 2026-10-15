"""
The 7 core question kinds (F-06 ERD 2.1, 2.3-2.6, 3.3).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from ..payload import QuestionPayload


@dataclass(frozen=True)
class KindSpec:
    name: str
    validate_payload: Callable[[QuestionPayload], list[str]]
    widget_key: str
    is_auto_gradable: bool = True
    answer_schema: dict[str, Any] | None = None


def validate_mcq_single(payload: QuestionPayload) -> list[str]:
    errors = []
    options = payload.get("options") or []
    if len(options) < 2 or len(options) > 6:
        errors.append(f"mcq_single must have between 2 and 6 options (found {len(options)}).")
    correct_count = sum(1 for opt in options if opt.get("is_correct"))
    if correct_count != 1:
        errors.append(f"mcq_single must have exactly 1 correct option (found {correct_count}).")
    return errors


def validate_mcq_multi(payload: QuestionPayload) -> list[str]:
    errors = []
    options = payload.get("options") or []
    if len(options) < 3 or len(options) > 8:
        errors.append(f"mcq_multi must have between 3 and 8 options (found {len(options)}).")
    correct_count = sum(1 for opt in options if opt.get("is_correct"))
    if correct_count < 1:
        errors.append("mcq_multi must have at least 1 correct option.")
    if correct_count >= len(options) and len(options) > 0:
        errors.append("mcq_multi cannot have all options marked correct.")
    return errors


def validate_true_false(payload: QuestionPayload) -> list[str]:
    errors = []
    options = payload.get("options") or []
    if len(options) != 2:
        errors.append(f"true_false must have exactly 2 options (found {len(options)}).")
    else:
        bodies = {opt.get("body_md", "").strip().lower() for opt in options}
        if bodies != {"true", "false"}:
            errors.append("true_false options must be 'True' and 'False'.")
    correct_count = sum(1 for opt in options if opt.get("is_correct"))
    if correct_count != 1:
        errors.append(f"true_false must have exactly 1 correct option (found {correct_count}).")
    return errors


def validate_numeric(payload: QuestionPayload) -> list[str]:
    errors = []
    num_key = payload.get("numeric_key")
    if not num_key or num_key.get("numeric_value") is None:
        errors.append("numeric question must provide an answer key with numeric_value.")
    return errors


def validate_case_study(payload: QuestionPayload) -> list[str]:
    errors = []
    children = payload.get("children") or []
    if not children:
        errors.append("case_study parent must have at least 1 child sub-question.")
    for idx, child in enumerate(children):
        if child.get("kind") == "case_study":
            errors.append(f"Child question at index {idx} cannot be a case_study.")
    return errors


def validate_long_form(payload: QuestionPayload) -> list[str]:
    errors = []
    rubric = payload.get("rubric")
    if not rubric or not rubric.get("reference_solution_md"):
        errors.append("long_form question requires a rubric with reference_solution_md.")
    steps = rubric.get("steps") if rubric else []
    if not steps:
        errors.append("long_form rubric must define at least one step.")
    else:
        try:
            total_step_marks = sum(Decimal(str(s.get("marks", 0))) for s in steps)
            total_marks = Decimal(str(payload.get("marks", 0)))
            if total_step_marks != total_marks:
                errors.append(f"Rubric steps sum ({total_step_marks}) does not equal question marks ({total_marks}).")
        except Exception:
            errors.append("Invalid marks value in rubric steps or question.")
    return errors


def validate_practical(payload: QuestionPayload) -> list[str]:
    # Same as long_form plus allows answer_template_md
    return validate_long_form(payload)


MCQ_SINGLE_SPEC = KindSpec(
    name="mcq_single",
    validate_payload=validate_mcq_single,
    widget_key="mcq_single",
    is_auto_gradable=True,
    answer_schema={"type": "object", "properties": {"selected_option_ids": {"type": "array", "maxItems": 1}}},
)

MCQ_MULTI_SPEC = KindSpec(
    name="mcq_multi",
    validate_payload=validate_mcq_multi,
    widget_key="mcq_multi",
    is_auto_gradable=True,
    answer_schema={"type": "object", "properties": {"selected_option_ids": {"type": "array"}}},
)

TRUE_FALSE_SPEC = KindSpec(
    name="true_false",
    validate_payload=validate_true_false,
    widget_key="true_false",
    is_auto_gradable=True,
    answer_schema={"type": "object", "properties": {"selected_option_ids": {"type": "array", "maxItems": 1}}},
)

NUMERIC_SPEC = KindSpec(
    name="numeric",
    validate_payload=validate_numeric,
    widget_key="numeric",
    is_auto_gradable=True,
    answer_schema={
        "type": "object",
        "properties": {"numeric_value": {"type": "number"}, "numeric_unit": {"type": "string"}},
    },
)

CASE_STUDY_SPEC = KindSpec(
    name="case_study",
    validate_payload=validate_case_study,
    widget_key="case_study",
    is_auto_gradable=False,
)

LONG_FORM_SPEC = KindSpec(
    name="long_form",
    validate_payload=validate_long_form,
    widget_key="long_form",
    is_auto_gradable=False,
)

PRACTICAL_SPEC = KindSpec(
    name="practical",
    validate_payload=validate_practical,
    widget_key="practical",
    is_auto_gradable=False,
)

ALL_KINDS = (
    MCQ_SINGLE_SPEC,
    MCQ_MULTI_SPEC,
    TRUE_FALSE_SPEC,
    NUMERIC_SPEC,
    CASE_STUDY_SPEC,
    LONG_FORM_SPEC,
    PRACTICAL_SPEC,
)
