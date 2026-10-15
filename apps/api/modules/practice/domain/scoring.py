"""
Pure scoring and grading domain logic (F-06 ERD 2.22, 3.2, 3.5).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Literal

from django.db.models import Q


@dataclass(frozen=True)
class ResolvedScoringRule:
    rule_id: uuid.UUID | None
    correct_mode: str  # "question_marks" | "fixed"
    fixed_correct_marks: Decimal | None
    negative_mode: str  # "none" | "fraction_of_marks" | "fixed"
    negative_value: Decimal  # e.g. 0.250 for 1/4th penalty
    skip_marks: Decimal
    multi_mode: str  # "all_or_nothing" | "partial_with_penalty" | "proportional"
    verified: bool
    source_note: str = ""

    def to_snapshot(self) -> dict:
        return {
            "v": 1,
            "rule_id": str(self.rule_id) if self.rule_id else None,
            "verified": self.verified,
            "correct_mode": self.correct_mode,
            "fixed_correct_marks": float(self.fixed_correct_marks) if self.fixed_correct_marks is not None else None,
            "negative_mode": self.negative_mode,
            "negative_value": float(self.negative_value),
            "skip_marks": float(self.skip_marks),
            "multi_mode": self.multi_mode,
            "source": self.source_note,
        }


DEFAULT_PRACTICE_RULE = ResolvedScoringRule(
    rule_id=None,
    correct_mode="question_marks",
    fixed_correct_marks=None,
    negative_mode="none",
    negative_value=Decimal("0.000"),
    skip_marks=Decimal("0.00"),
    multi_mode="all_or_nothing",
    verified=False,
    source_note="Default practice rule (no negative marking)",
)


def compute_negative_penalty(rule: ResolvedScoringRule, marks_max: Decimal) -> Decimal:
    """Compute the negative marking penalty for an incorrect answer."""
    if rule.negative_mode == "fraction_of_marks":
        return round(marks_max * rule.negative_value, 2)
    elif rule.negative_mode == "fixed":
        return round(rule.negative_value, 2)
    return Decimal("0.00")


@dataclass(frozen=True)
class GradingResult:
    result: Literal["correct", "incorrect", "partial", "skipped", "pending", "ungraded"]
    marks_awarded: Decimal
    negative_applied: Decimal


@dataclass(frozen=True)
class OptionKey:
    id: uuid.UUID
    is_correct: bool


@dataclass(frozen=True)
class NumericKey:
    numeric_value: Decimal
    tolerance_abs: Decimal = Decimal("0.000000")
    tolerance_rel: Decimal = Decimal("0.0000")
    accepted_values: list[Decimal] = field(default_factory=list)


def grade_choice(
    kind: str,
    selected_option_ids: list[uuid.UUID],
    options: list[OptionKey],
    marks_max: Decimal,
    negative_max: Decimal,
    multi_mode: str = "all_or_nothing",
) -> GradingResult:
    """Pure grading of choice-based questions (mcq_single, mcq_multi, true_false)."""
    if not selected_option_ids:
        return GradingResult(result="skipped", marks_awarded=Decimal("0.00"), negative_applied=Decimal("0.00"))

    selected_set = set(selected_option_ids)
    correct_set = {opt.id for opt in options if opt.is_correct}
    incorrect_set = {opt.id for opt in options if not opt.is_correct}

    if kind in ("mcq_single", "true_false"):
        if len(selected_set) == 1 and selected_set == correct_set:
            return GradingResult(result="correct", marks_awarded=marks_max, negative_applied=Decimal("0.00"))
        else:
            return GradingResult(result="incorrect", marks_awarded=-negative_max, negative_applied=negative_max)

    # mcq_multi
    if selected_set == correct_set:
        return GradingResult(result="correct", marks_awarded=marks_max, negative_applied=Decimal("0.00"))

    if multi_mode == "all_or_nothing":
        if selected_set & incorrect_set:
            return GradingResult(result="incorrect", marks_awarded=-negative_max, negative_applied=negative_max)
        else:
            return GradingResult(result="incorrect", marks_awarded=Decimal("0.00"), negative_applied=Decimal("0.00"))

    elif multi_mode in ("partial_with_penalty", "partial_strict"):
        # If any selected option is wrong, award no marks and apply negative penalty
        if selected_set & incorrect_set:
            return GradingResult(result="incorrect", marks_awarded=-negative_max, negative_applied=negative_max)
        # If student picked only correct options (but not all)
        if selected_set.issubset(correct_set) and correct_set:
            ratio = Decimal(len(selected_set)) / Decimal(len(correct_set))
            awarded = round(marks_max * ratio, 2)
            return GradingResult(result="partial", marks_awarded=awarded, negative_applied=Decimal("0.00"))
        return GradingResult(result="incorrect", marks_awarded=-negative_max, negative_applied=negative_max)

    elif multi_mode == "proportional":
        correct_chosen = len(selected_set & correct_set)
        incorrect_chosen = len(selected_set & incorrect_set)
        total_correct = len(correct_set) or 1
        total_incorrect = len(incorrect_set) or 1

        gain = marks_max * (Decimal(correct_chosen) / Decimal(total_correct))
        loss = negative_max * (Decimal(incorrect_chosen) / Decimal(total_incorrect))
        net = round(gain - loss, 2)
        net = max(-negative_max, net)

        if net > 0:
            return GradingResult(result="partial", marks_awarded=net, negative_applied=Decimal("0.00"))
        else:
            neg_applied = max(Decimal("0.00"), -net)
            return GradingResult(result="incorrect", marks_awarded=net, negative_applied=neg_applied)

    return GradingResult(result="incorrect", marks_awarded=-negative_max, negative_applied=negative_max)


def grade_numeric(
    student_value: Decimal | None,
    key: NumericKey,
    marks_max: Decimal,
    negative_max: Decimal,
) -> GradingResult:
    """Pure grading of numeric kind."""
    if student_value is None:
        return GradingResult(result="skipped", marks_awarded=Decimal("0.00"), negative_applied=Decimal("0.00"))

    def _matches(val: Decimal, target: Decimal, tol_abs: Decimal, tol_rel: Decimal) -> bool:
        tol = max(tol_abs, tol_rel * abs(target))
        return abs(val - target) <= tol

    if _matches(student_value, key.numeric_value, key.tolerance_abs, key.tolerance_rel):
        return GradingResult(result="correct", marks_awarded=marks_max, negative_applied=Decimal("0.00"))

    for alt in key.accepted_values:
        alt_dec = Decimal(str(alt))
        if _matches(student_value, alt_dec, key.tolerance_abs, key.tolerance_rel):
            return GradingResult(result="correct", marks_awarded=marks_max, negative_applied=Decimal("0.00"))

    return GradingResult(result="incorrect", marks_awarded=-negative_max, negative_applied=negative_max)


def resolve_scoring_rule(
    course_id: uuid.UUID,
    level_id: uuid.UUID | None = None,
    subject_key: str | None = None,
    question_kind: str | None = None,
    on_date: date | None = None,
    profile: str = "practice",
) -> ResolvedScoringRule:
    """
    Resolve scoring rule following ERD 2.22 specificity rules:
    (level, subject_key, kind) -> (level, subject_key) -> (level, kind) -> (level) -> (course, kind) -> (course)
    """
    if profile != "official":
        return DEFAULT_PRACTICE_RULE

    from ..models import ScoringRule

    target_date = on_date or date.today()

    qs = ScoringRule.objects.filter(
        course_id=course_id,
        status=ScoringRule.Status.ACTIVE,
        verified=True,
        effective_from__lte=target_date,
    ).filter(Q(effective_to__isnull=True) | Q(effective_to__gte=target_date))

    # Cascade lookup
    rules = list(qs)
    if not rules:
        return DEFAULT_PRACTICE_RULE

    def match(r: ScoringRule, match_level: bool, match_subject: bool, match_kind: bool) -> bool:
        lvl_ok = (r.level_id == level_id) if match_level else (r.level_id is None)
        sub_ok = (r.subject_key == subject_key) if match_subject else not r.subject_key
        knd_ok = (r.question_kind == question_kind) if match_kind else not r.question_kind
        return lvl_ok and sub_ok and knd_ok

    candidates = [
        # (level, subject_key, kind)
        (True, True, True),
        # (level, subject_key)
        (True, True, False),
        # (level, kind)
        (True, False, True),
        # (level)
        (True, False, False),
        # (course, kind)
        (False, False, True),
        # (course)
        (False, False, False),
    ]

    for mL, mS, mK in candidates:
        for r in rules:
            if match(r, mL, mS, mK):
                return ResolvedScoringRule(
                    rule_id=r.id,
                    correct_mode=r.correct_mode,
                    fixed_correct_marks=r.fixed_correct_marks,
                    negative_mode=r.negative_mode,
                    negative_value=r.negative_value,
                    skip_marks=r.skip_marks,
                    multi_mode=r.multi_mode,
                    verified=r.verified,
                    source_note=r.source_note,
                )

    return DEFAULT_PRACTICE_RULE
