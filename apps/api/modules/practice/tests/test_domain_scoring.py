"""
Tests for scoring domain logic: MCQ grading, numeric grading, negative marks, and property tests.
"""

from decimal import Decimal
from uuid import uuid4

from hypothesis import given, settings
from hypothesis import strategies as st

from modules.practice.domain.scoring import (
    NumericKey,
    OptionKey,
    grade_choice,
    grade_numeric,
)


def test_mcq_single_correct():
    opt1, opt2 = uuid4(), uuid4()
    options = [
        OptionKey(id=opt1, is_correct=True),
        OptionKey(id=opt2, is_correct=False),
    ]
    res = grade_choice(
        kind="mcq_single",
        selected_option_ids=[opt1],
        options=options,
        marks_max=Decimal("2.0"),
        negative_max=Decimal("0.5"),
    )
    assert res.result == "correct"
    assert res.marks_awarded == Decimal("2.0")
    assert res.negative_applied == Decimal("0.0")


def test_mcq_single_incorrect_applies_negative():
    opt1, opt2 = uuid4(), uuid4()
    options = [
        OptionKey(id=opt1, is_correct=True),
        OptionKey(id=opt2, is_correct=False),
    ]
    res = grade_choice(
        kind="mcq_single",
        selected_option_ids=[opt2],
        options=options,
        marks_max=Decimal("2.0"),
        negative_max=Decimal("0.5"),
    )
    assert res.result == "incorrect"
    assert res.marks_awarded == Decimal("-0.5")
    assert res.negative_applied == Decimal("0.5")


def test_mcq_single_unanswered():
    opt1, opt2 = uuid4(), uuid4()
    options = [
        OptionKey(id=opt1, is_correct=True),
        OptionKey(id=opt2, is_correct=False),
    ]
    res = grade_choice(
        kind="mcq_single",
        selected_option_ids=[],
        options=options,
        marks_max=Decimal("2.0"),
        negative_max=Decimal("0.5"),
    )
    assert res.result == "skipped"
    assert res.marks_awarded == Decimal("0.0")
    assert res.negative_applied == Decimal("0.0")


def test_true_false_grading():
    opt_t, opt_f = uuid4(), uuid4()
    options = [
        OptionKey(id=opt_t, is_correct=False),
        OptionKey(id=opt_f, is_correct=True),
    ]
    res = grade_choice(
        kind="true_false",
        selected_option_ids=[opt_f],
        options=options,
        marks_max=Decimal("1.0"),
        negative_max=Decimal("0.25"),
    )
    assert res.result == "correct"
    assert res.marks_awarded == Decimal("1.0")


def test_mcq_multi_all_or_nothing():
    o1, o2, o3 = uuid4(), uuid4(), uuid4()
    options = [
        OptionKey(id=o1, is_correct=True),
        OptionKey(id=o2, is_correct=True),
        OptionKey(id=o3, is_correct=False),
    ]
    # Partially correct selection with all_or_nothing gives 0
    res = grade_choice(
        kind="mcq_multi",
        selected_option_ids=[o1],
        options=options,
        marks_max=Decimal("2.0"),
        negative_max=Decimal("0.5"),
        multi_mode="all_or_nothing",
    )
    assert res.result == "incorrect"
    assert res.marks_awarded == Decimal("0.0")

    # Full correct
    res2 = grade_choice(
        kind="mcq_multi",
        selected_option_ids=[o1, o2],
        options=options,
        marks_max=Decimal("2.0"),
        negative_max=Decimal("0.5"),
        multi_mode="all_or_nothing",
    )
    assert res2.result == "correct"
    assert res2.marks_awarded == Decimal("2.0")


def test_mcq_multi_partial_strict():
    o1, o2, o3 = uuid4(), uuid4(), uuid4()
    options = [
        OptionKey(id=o1, is_correct=True),
        OptionKey(id=o2, is_correct=True),
        OptionKey(id=o3, is_correct=False),
    ]
    # Selecting 1 of 2 correct with no wrong selections gives partial credit
    res = grade_choice(
        kind="mcq_multi",
        selected_option_ids=[o1],
        options=options,
        marks_max=Decimal("2.0"),
        negative_max=Decimal("0.5"),
        multi_mode="partial_strict",
    )
    assert res.result == "partial"
    assert res.marks_awarded == Decimal("1.0")

    # Selecting 1 correct and 1 wrong gives negative marks
    res2 = grade_choice(
        kind="mcq_multi",
        selected_option_ids=[o1, o3],
        options=options,
        marks_max=Decimal("2.0"),
        negative_max=Decimal("0.5"),
        multi_mode="partial_strict",
    )
    assert res2.result == "incorrect"
    assert res2.marks_awarded == Decimal("-0.5")


def test_numeric_exact_match():
    key = NumericKey(
        numeric_value=Decimal("150.50"),
        tolerance_abs=Decimal("0.0"),
        tolerance_rel=Decimal("0.0"),
    )
    res = grade_numeric(
        student_value=Decimal("150.50"),
        key=key,
        marks_max=Decimal("4.0"),
        negative_max=Decimal("1.0"),
    )
    assert res.result == "correct"
    assert res.marks_awarded == Decimal("4.0")


def test_numeric_within_absolute_tolerance():
    key = NumericKey(
        numeric_value=Decimal("100.00"),
        tolerance_abs=Decimal("2.0"),
        tolerance_rel=Decimal("0.0"),
    )
    res = grade_numeric(
        student_value=Decimal("101.50"),
        key=key,
        marks_max=Decimal("2.0"),
        negative_max=Decimal("0.5"),
    )
    assert res.result == "correct"
    assert res.marks_awarded == Decimal("2.0")


def test_numeric_within_relative_tolerance():
    key = NumericKey(
        numeric_value=Decimal("200.00"),
        tolerance_abs=Decimal("0.0"),
        tolerance_rel=Decimal("0.05"),  # 5%
    )
    res = grade_numeric(
        student_value=Decimal("208.00"),  # 4% off
        key=key,
        marks_max=Decimal("2.0"),
        negative_max=Decimal("0.5"),
    )
    assert res.result == "correct"

    res_out = grade_numeric(
        student_value=Decimal("220.00"),  # 10% off
        key=key,
        marks_max=Decimal("2.0"),
        negative_max=Decimal("0.5"),
    )
    assert res_out.result == "incorrect"
    assert res_out.marks_awarded == Decimal("-0.5")


def test_numeric_alternate_accepted_values():
    key = NumericKey(
        numeric_value=Decimal("10.0"),
        tolerance_abs=Decimal("0.0"),
        tolerance_rel=Decimal("0.0"),
        accepted_values=["10.5", "11.0"],
    )
    res = grade_numeric(
        student_value=Decimal("10.5"),
        key=key,
        marks_max=Decimal("1.0"),
        negative_max=Decimal("0.0"),
    )
    assert res.result == "correct"


# Property-based testing with Hypothesis
@given(
    marks=st.decimals(min_value=Decimal("0.5"), max_value=Decimal("10.0"), places=2),
    negative=st.decimals(min_value=Decimal("0.0"), max_value=Decimal("5.0"), places=2),
)
@settings(max_examples=30)
def test_property_negative_marking_never_exceeds_max_penalty(marks, negative):
    opt1, opt2 = uuid4(), uuid4()
    options = [
        OptionKey(id=opt1, is_correct=True),
        OptionKey(id=opt2, is_correct=False),
    ]
    res = grade_choice(
        kind="mcq_single",
        selected_option_ids=[opt2],
        options=options,
        marks_max=marks,
        negative_max=negative,
    )
    assert res.negative_applied <= negative
    assert res.marks_awarded >= -negative
