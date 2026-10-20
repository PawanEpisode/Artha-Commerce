from datetime import date

from modules.amendments.domain.applicability import (
    ApplicabilityStatus,
    DocumentTermRule,
    evaluate_applicability,
)


def test_student_without_term_returns_unknown():
    res = evaluate_applicability(
        student_term=None,
        document_terms=[DocumentTermRule(term_code="2026-05")],
    )
    assert res.status == ApplicabilityStatus.UNKNOWN
    assert res.reason_code == "no_student_term"
    assert res.is_unknown


def test_explicit_applies_without_card_effective_term():
    rules = [
        DocumentTermRule(term_code="2026-05", applicability="applies", cutoff_date=date(2025, 10, 31)),
        DocumentTermRule(term_code="2026-11", applicability="applies"),
    ]
    res = evaluate_applicability(student_term="2026-05", document_terms=rules)
    assert res.status == ApplicabilityStatus.APPLIES
    assert res.reason_code == "applies_to_term"
    assert res.is_applicable
    assert "2025-10-31" in res.reason_text


def test_explicit_applies_with_card_effective_term_in_future():
    rules = [
        DocumentTermRule(term_code="2026-05", applicability="applies"),
        DocumentTermRule(term_code="2026-11", applicability="applies"),
    ]
    # Card is only effective from November 2026
    res = evaluate_applicability(
        student_term="2026-05",
        document_terms=rules,
        card_effective_term="2026-11",
    )
    assert res.status == ApplicabilityStatus.NOT_APPLICABLE
    assert res.reason_code == "effective_from_later"
    assert res.is_not_applicable


def test_explicit_applies_with_card_effective_term_in_past_or_same():
    rules = [
        DocumentTermRule(term_code="2026-11", applicability="applies"),
    ]
    # Card was already effective from May 2026
    res = evaluate_applicability(
        student_term="2026-11",
        document_terms=rules,
        card_effective_term="2026-05",
    )
    assert res.status == ApplicabilityStatus.APPLIES
    assert res.reason_code == "applies_to_term"


def test_explicit_excluded_term():
    rules = [
        DocumentTermRule(term_code="2026-05", applicability="excluded"),
        DocumentTermRule(term_code="2026-11", applicability="applies"),
    ]
    res = evaluate_applicability(student_term="2026-05", document_terms=rules)
    assert res.status == ApplicabilityStatus.NOT_APPLICABLE
    assert res.reason_code == "institute_excluded"
    assert res.is_not_applicable


def test_empty_document_terms_returns_unknown():
    res = evaluate_applicability(student_term="2026-05", document_terms=[])
    assert res.status == ApplicabilityStatus.UNKNOWN
    assert res.reason_code == "no_declared_terms"


def test_student_term_earlier_than_all_declared_terms():
    rules = [
        DocumentTermRule(term_code="2026-11", applicability="applies"),
        DocumentTermRule(term_code="2027-05", applicability="applies"),
    ]
    # Student target term is May 2026 (earlier than all declared)
    res = evaluate_applicability(student_term="2026-05", document_terms=rules)
    assert res.status == ApplicabilityStatus.NOT_APPLICABLE
    assert res.reason_code == "meant_for_later_attempts"


def test_student_term_later_than_declared_terms_returns_unknown():
    rules = [
        DocumentTermRule(term_code="2025-05", applicability="applies"),
        DocumentTermRule(term_code="2025-11", applicability="applies"),
    ]
    # Student target term is May 2026 (later than declared; cannot assume carry-forward)
    res = evaluate_applicability(student_term="2026-05", document_terms=rules)
    assert res.status == ApplicabilityStatus.UNKNOWN
    assert res.reason_code == "rule_not_published"
