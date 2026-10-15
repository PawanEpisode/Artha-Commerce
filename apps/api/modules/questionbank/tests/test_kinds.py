from decimal import Decimal

from modules.questionbank.registry import get_kind, registered_kinds


def test_all_seven_kinds_are_registered():
    kinds = registered_kinds()
    assert len(kinds) == 7
    expected = {
        "mcq_single",
        "mcq_multi",
        "true_false",
        "numeric",
        "case_study",
        "long_form",
        "practical",
    }
    assert set(kinds.keys()) == expected


def test_mcq_single_validation():
    spec = get_kind("mcq_single")
    # Valid: 4 options, 1 correct
    valid_payload = {
        "kind": "mcq_single",
        "options": [
            {"body_md": "A", "is_correct": True},
            {"body_md": "B", "is_correct": False},
            {"body_md": "C", "is_correct": False},
            {"body_md": "D", "is_correct": False},
        ],
    }
    assert spec.validate_payload(valid_payload) == []

    # Invalid: 2 correct
    invalid_2_correct = {
        "kind": "mcq_single",
        "options": [
            {"body_md": "A", "is_correct": True},
            {"body_md": "B", "is_correct": True},
        ],
    }
    assert len(spec.validate_payload(invalid_2_correct)) > 0

    # Invalid: 1 option only
    invalid_1_opt = {
        "kind": "mcq_single",
        "options": [{"body_md": "A", "is_correct": True}],
    }
    assert len(spec.validate_payload(invalid_1_opt)) > 0


def test_mcq_multi_validation():
    spec = get_kind("mcq_multi")
    # Valid: 4 options, 2 correct
    valid_payload = {
        "kind": "mcq_multi",
        "options": [
            {"body_md": "A", "is_correct": True},
            {"body_md": "B", "is_correct": True},
            {"body_md": "C", "is_correct": False},
            {"body_md": "D", "is_correct": False},
        ],
    }
    assert spec.validate_payload(valid_payload) == []

    # Invalid: 0 correct
    invalid_0_correct = {
        "kind": "mcq_multi",
        "options": [
            {"body_md": "A", "is_correct": False},
            {"body_md": "B", "is_correct": False},
            {"body_md": "C", "is_correct": False},
        ],
    }
    assert len(spec.validate_payload(invalid_0_correct)) > 0

    # Invalid: all correct
    invalid_all_correct = {
        "kind": "mcq_multi",
        "options": [
            {"body_md": "A", "is_correct": True},
            {"body_md": "B", "is_correct": True},
            {"body_md": "C", "is_correct": True},
        ],
    }
    assert len(spec.validate_payload(invalid_all_correct)) > 0


def test_true_false_validation():
    spec = get_kind("true_false")
    valid_payload = {
        "kind": "true_false",
        "options": [
            {"body_md": "True", "is_correct": True},
            {"body_md": "False", "is_correct": False},
        ],
    }
    assert spec.validate_payload(valid_payload) == []

    # Invalid: 3 options
    invalid_3_opts = {
        "kind": "true_false",
        "options": [
            {"body_md": "True", "is_correct": True},
            {"body_md": "False", "is_correct": False},
            {"body_md": "Maybe", "is_correct": False},
        ],
    }
    assert len(spec.validate_payload(invalid_3_opts)) > 0


def test_numeric_validation():
    spec = get_kind("numeric")
    valid_payload = {
        "kind": "numeric",
        "numeric_key": {"numeric_value": Decimal("100.5"), "tolerance_abs": Decimal("0.5")},
    }
    assert spec.validate_payload(valid_payload) == []

    invalid_no_key = {"kind": "numeric"}
    assert len(spec.validate_payload(invalid_no_key)) > 0


def test_case_study_validation():
    spec = get_kind("case_study")
    valid_payload = {
        "kind": "case_study",
        "children": [
            {"kind": "mcq_single", "stem_md": "Child 1"},
            {"kind": "numeric", "stem_md": "Child 2"},
        ],
    }
    assert spec.validate_payload(valid_payload) == []

    # Invalid: child cannot be case_study
    invalid_nested = {
        "kind": "case_study",
        "children": [{"kind": "case_study", "stem_md": "Nested child"}],
    }
    assert len(spec.validate_payload(invalid_nested)) > 0


def test_long_form_validation():
    spec = get_kind("long_form")
    valid_payload = {
        "kind": "long_form",
        "marks": Decimal("10.0"),
        "rubric": {
            "reference_solution_md": "Model solution",
            "steps": [
                {"title": "Step 1", "marks": Decimal("6.0")},
                {"title": "Step 2", "marks": Decimal("4.0")},
            ],
        },
    }
    assert spec.validate_payload(valid_payload) == []

    # Invalid: step marks do not sum to total marks
    invalid_sum = {
        "kind": "long_form",
        "marks": Decimal("10.0"),
        "rubric": {
            "reference_solution_md": "Model solution",
            "steps": [
                {"title": "Step 1", "marks": Decimal("5.0")},
                {"title": "Step 2", "marks": Decimal("4.0")},
            ],
        },
    }
    assert len(spec.validate_payload(invalid_sum)) > 0
