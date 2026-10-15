"""
Domain tests for PYQ: marks tree, choice rules, schema validation, link checks, and no-user_id invariant.
"""

from __future__ import annotations

from decimal import Decimal

from modules.pyq.domain.choice import validate_choice_groups
from modules.pyq.domain.importer import validate_paper_payload
from modules.pyq.domain.links import validate_paper_link
from modules.pyq.domain.marks import validate_marks_tree
from modules.pyq.models import (
    AskedCache,
    ChoiceGroup,
    DailySet,
    DailySetItem,
    PaperLink,
    PaperQuestion,
    PyqPaper,
)


def test_no_user_id_columns_in_pyq():
    """Security/privacy invariant: pyq owns no personal student data and has no user_id column."""
    models = [PyqPaper, ChoiceGroup, PaperQuestion, PaperLink, AskedCache, DailySet, DailySetItem]
    for model in models:
        field_names = [f.name for f in model._meta.get_fields()]
        assert "user_id" not in field_names, f"Model {model.__name__} must not have a user_id column!"


def test_marks_tree_interior_validation():
    # Valid interior: Q.1 (marks=10) has children 1(a)=6 and 1(b)=4
    parts = [
        {"id": "q1", "number_label": "1", "marks": Decimal("10.00"), "parent_id": None},
        {"id": "q1a", "number_label": "1(a)", "marks": Decimal("6.00"), "parent_id": "q1"},
        {"id": "q1b", "number_label": "1(b)", "marks": Decimal("4.00"), "parent_id": "q1"},
    ]
    issues = validate_marks_tree(parts, total_marks=Decimal("10.00"))
    assert len(issues) == 0

    # Invalid interior: Q.1 marks=12 != 6 + 4
    parts[0]["marks"] = Decimal("12.00")
    issues = validate_marks_tree(parts, total_marks=Decimal("12.00"))
    assert any("interior marks 12.00 do not equal children sum 10.00" in err for err in issues)


def test_choice_group_rules_validation():
    # Compulsory: pick_count == of_count
    cg_compulsory = [{"label": "Q1", "rule_kind": "compulsory", "pick_count": 1, "of_count": 1}]
    top_parts = [{"number_label": "1", "choice_group_ref": "Q1"}]
    assert len(validate_choice_groups(cg_compulsory, top_parts)) == 0

    # any_n_of_m: pick_count < of_count, and count of matching parts == of_count
    cg_choice = [{"label": "Section B", "rule_kind": "any_n_of_m", "pick_count": 4, "of_count": 5}]
    top_parts_choice = [
        {"number_label": "2", "choice_group_ref": "Section B"},
        {"number_label": "3", "choice_group_ref": "Section B"},
        {"number_label": "4", "choice_group_ref": "Section B"},
        {"number_label": "5", "choice_group_ref": "Section B"},
        {"number_label": "6", "choice_group_ref": "Section B"},
    ]
    assert len(validate_choice_groups(cg_choice, top_parts_choice)) == 0


def test_link_validation():
    # Valid official links
    valid, host, _ = validate_paper_link("https://icmai.in/upload/Students/Question_Papers/Inter_June2024.pdf")
    assert valid is True
    assert host == "icmai.in"

    valid, host, _ = validate_paper_link("https://www.icai.org/post/question-papers-intermediate")
    assert valid is True

    # Invalid: non-HTTPS
    valid, _, msg = validate_paper_link("http://icmai.in/paper.pdf")
    assert valid is False
    assert "HTTPS" in msg

    # Invalid: untrusted host
    valid, _, msg = validate_paper_link("https://sketchy-download-site.com/paper.pdf")
    assert valid is False
    assert "not on the PYQ link allow-list" in msg


def test_paper_payload_validation():
    valid_payload = {
        "external_ref": "pyq:cma:inter:taxation:2024-06",
        "course_code": "cma",
        "level_code": "intermediate",
        "subject_key": "taxation",
        "term_code": "2024-06",
        "title": "CMA Intermediate June 2024 Paper 7",
        "total_marks": 100.0,
        "delivery": "link_out",
        "links": [
            {
                "link_kind": "paper",
                "url": "https://icmai.in/paper.pdf",
            }
        ],
        "parts": [
            {
                "number_label": "1",
                "depth": 0,
                "marks": 100.0,
                "is_leaf": True,
            }
        ],
    }
    errors = validate_paper_payload(valid_payload)
    assert len(errors) == 0

    # Missing term_code and invalid delivery
    invalid_payload = {**valid_payload, "term_code": "invalid-term", "delivery": "invalid_mode"}
    errors = validate_paper_payload(invalid_payload)
    assert len(errors) > 0
