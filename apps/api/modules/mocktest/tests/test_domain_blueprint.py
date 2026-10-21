"""
Tests for blueprint domain validation and hashing.
"""

from decimal import Decimal
import uuid
from modules.mocktest.domain import blueprint


def test_blueprint_validation_success():
    sections = [
        {"key": "A", "title": "Objective", "duration_seconds": 3600},
        {"key": "B", "title": "Descriptive", "duration_seconds": 7200},
    ]
    q1 = uuid.uuid4()
    q2 = uuid.uuid4()
    q3 = uuid.uuid4()

    items = [
        {"position": 1, "question_id": q1, "section_key": "A", "marks": 2},
        {"position": 2, "question_id": q2, "section_key": "B", "marks": 5, "choice_group_key": "G1"},
        {"position": 3, "question_id": q3, "section_key": "B", "marks": 5, "choice_group_key": "G1"},
    ]
    groups = [
        {"key": "G1", "section_key": "B", "required_count": 1, "label": "Answer 1 of 2"}
    ]

    is_valid, problems, total = blueprint.validate_blueprint(
        sections=sections,
        items=items,
        choice_groups=groups,
        section_timing="sequential",
    )
    assert is_valid is True
    assert len(problems) == 0
    # Total marks: 2 (from pos 1) + 1 * 5 (from choice group G1) = 7
    assert total == Decimal("7")


def test_blueprint_validation_unequal_marks_in_choice_group():
    sections = [{"key": "A", "title": "Section A"}]
    items = [
        {"position": 1, "question_id": uuid.uuid4(), "section_key": "A", "marks": 4, "choice_group_key": "G1"},
        {"position": 2, "question_id": uuid.uuid4(), "section_key": "A", "marks": 6, "choice_group_key": "G1"},
    ]
    groups = [{"key": "G1", "section_key": "A", "required_count": 1, "label": "Answer 1 of 2"}]

    is_valid, problems, _ = blueprint.validate_blueprint(sections=sections, items=items, choice_groups=groups)
    assert is_valid is False
    assert any("equal marks" in p for p in problems)
