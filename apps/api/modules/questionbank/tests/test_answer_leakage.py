from decimal import Decimal

import pytest

from modules.questionbank.selectors import get_playable
from modules.questionbank.services import create_draft, publish_version
from modules.questionbank.tests.conftest import EDITOR, USER

pytestmark = pytest.mark.django_db

FORBIDDEN_KEYS = {
    "is_correct",
    "numeric_value",
    "tolerance_abs",
    "tolerance_rel",
    "accepted_values",
    "explanation_md",
    "explanation_source",
    "rubric",
    "feedback_md",
    "reference_solution_md",
}


def assert_no_leakage(obj):
    """Recursively asserts that no forbidden answer keys exist in any dictionary or dataclass."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            assert k not in FORBIDDEN_KEYS, f"Leaked forbidden key '{k}' in payload"
            assert_no_leakage(v)
    elif isinstance(obj, (list, tuple)):
        for item in obj:
            assert_no_leakage(item)
    elif hasattr(obj, "__dict__"):
        assert_no_leakage(obj.__dict__)


def test_mcq_playable_does_not_leak_correct_option_or_feedback():
    payload = {
        "kind": "mcq_single",
        "stem_md": "What is ITC?",
        "explanation_md": "ITC is Input Tax Credit under Section 16 of CGST Act.",
        "options": [
            {"body_md": "Input Tax Credit", "is_correct": True, "feedback_md": "Yes, correct!"},
            {"body_md": "Income Tax Credit", "is_correct": False, "feedback_md": "Wrong"},
        ],
    }
    q = create_draft(USER, payload)
    ver = publish_version(EDITOR, q.current_version.id, visibility="public")

    playable = get_playable(q.id, ver.id)
    assert_no_leakage(playable)

    # Specific assertions
    for opt in playable.options:
        assert not hasattr(opt, "is_correct")
        assert not hasattr(opt, "feedback_md")


def test_numeric_playable_does_not_leak_numeric_value_or_tolerances():
    payload = {
        "kind": "numeric",
        "stem_md": "What is 15% of 1,00,000?",
        "explanation_md": "15% of 1,00,000 is 15,000.",
        "numeric_key": {
            "numeric_value": Decimal("15000"),
            "tolerance_abs": Decimal("10"),
            "tolerance_rel": Decimal("0.01"),
            "accepted_values": [Decimal("15000")],
            "unit": "Rs",
            "unit_required": True,
        },
    }
    q = create_draft(USER, payload)
    ver = publish_version(EDITOR, q.current_version.id, visibility="public")

    playable = get_playable(q.id, ver.id)
    assert_no_leakage(playable)

    # Unit and unit_required are allowed for students to know the expected format; numeric value is not!
    assert playable.numeric == {"unit": "Rs", "unit_required": True}


def test_long_form_playable_does_not_leak_rubric_or_steps():
    payload = {
        "kind": "long_form",
        "stem_md": "Explain the concept of Reverse Charge Mechanism under Section 9(3).",
        "marks": Decimal("5.0"),
        "rubric": {
            "reference_solution_md": "Under RCM, the recipient is liable to pay tax instead of the supplier.",
            "steps": [
                {"title": "Definition of RCM", "marks": Decimal("2.0")},
                {"title": "Section 9(3) notifications", "marks": Decimal("3.0")},
            ],
        },
    }
    q = create_draft(USER, payload)
    ver = publish_version(EDITOR, q.current_version.id, visibility="public")

    playable = get_playable(q.id, ver.id)
    assert_no_leakage(playable)
    assert not hasattr(playable, "rubric")
