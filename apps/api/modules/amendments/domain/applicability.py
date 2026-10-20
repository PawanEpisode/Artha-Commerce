from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import StrEnum


class ApplicabilityStatus(StrEnum):
    APPLIES = "applies"
    NOT_APPLICABLE = "not_applicable"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class DocumentTermRule:
    term_code: str
    applicability: str = "applies"  # "applies" or "excluded"
    cutoff_date: date | None = None
    cutoff_note: str = ""


@dataclass(frozen=True)
class ApplicabilityResult:
    status: ApplicabilityStatus
    reason_code: str
    reason_text: str

    @property
    def is_applicable(self) -> bool:
        return self.status == ApplicabilityStatus.APPLIES

    @property
    def is_unknown(self) -> bool:
        return self.status == ApplicabilityStatus.UNKNOWN

    @property
    def is_not_applicable(self) -> bool:
        return self.status == ApplicabilityStatus.NOT_APPLICABLE


def evaluate_applicability(
    student_term: str | None,
    document_terms: list[DocumentTermRule],
    card_effective_term: str | None = None,
) -> ApplicabilityResult:
    """
    Pure decision function implementing PRD Section 5.3:
    Evaluates whether an amendment card applies to a student's attempt.

    Arguments:
        student_term: The student's target exam term code (e.g., '2026-05', '2026-11').
        document_terms: List of term applicability rules for the parent document revision.
        card_effective_term: Optional term code from which this specific card takes effect.

    Returns:
        ApplicabilityResult containing status ('applies', 'not_applicable', 'unknown'),
        a machine-readable reason code, and user-facing explanation.
    """
    if not student_term:
        return ApplicabilityResult(
            status=ApplicabilityStatus.UNKNOWN,
            reason_code="no_student_term",
            reason_text="Set your target exam attempt to see applicability.",
        )

    # 1. Check if document has an explicit row for the student's term
    matching_rule = next((rule for rule in document_terms if rule.term_code == student_term), None)

    if matching_rule:
        if matching_rule.applicability == "excluded":
            return ApplicabilityResult(
                status=ApplicabilityStatus.NOT_APPLICABLE,
                reason_code="institute_excluded",
                reason_text="The Institute explicitly excludes this amendment from your attempt.",
            )

        # Rule says "applies", now check if card itself is effective from a later term
        if card_effective_term and student_term < card_effective_term:
            return ApplicabilityResult(
                status=ApplicabilityStatus.NOT_APPLICABLE,
                reason_code="effective_from_later",
                reason_text=f"This change only takes effect from attempt {card_effective_term}.",
            )

        cutoff_msg = f" (Cut-off date: {matching_rule.cutoff_date})" if matching_rule.cutoff_date else ""
        return ApplicabilityResult(
            status=ApplicabilityStatus.APPLIES,
            reason_code="applies_to_term",
            reason_text=f"Applicable for your {student_term} attempt{cutoff_msg}.",
        )

    # 2. No explicit row for this student's term
    if not document_terms:
        return ApplicabilityResult(
            status=ApplicabilityStatus.UNKNOWN,
            reason_code="no_declared_terms",
            reason_text="The Institute has not declared applicable exam terms yet.",
        )

    declared_terms = [rule.term_code for rule in document_terms]
    min_term = min(declared_terms)

    # If student's attempt is strictly earlier than all declared applicable terms,
    # it is meant for later exam attempts and does not apply.
    if student_term < min_term:
        return ApplicabilityResult(
            status=ApplicabilityStatus.NOT_APPLICABLE,
            reason_code="meant_for_later_attempts",
            reason_text="This amendment applies to exam attempts after your target attempt.",
        )

    # Student term is later than or between declared terms without explicit declaration
    return ApplicabilityResult(
        status=ApplicabilityStatus.UNKNOWN,
        reason_code="rule_not_published",
        reason_text=f"The Institute has not published the amendments rule for {student_term} yet.",
    )
