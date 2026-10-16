from decimal import Decimal

from modules.questionbank.domain.difficulty import estimate_difficulty


def test_plain_recall_mcq_is_easy_to_moderate():
    d = estimate_difficulty(
        kind="mcq_single",
        stem="What is the time limit for filing GSTR-3B?",
        options=["20th of next month", "10th", "30th", "1st"],
    )
    assert 1 <= d <= 3


def test_statement_and_trap_options_raise_difficulty():
    easy = estimate_difficulty(kind="mcq_single", stem="Capital of India?", options=["Delhi", "Pune"])
    hard = estimate_difficulty(
        kind="mcq_single",
        stem="Consider the following statements under Section 16 of the CGST Act. Which is not correct?",
        options=["Both I and II", "Only I", "None of the above", "All of the above"],
    )
    assert hard > easy


def test_long_form_marks_matter():
    stem = "Calculate the net profit under marginal costing."
    small = estimate_difficulty(kind="long_form", stem=stem, marks=Decimal("2"))
    big = estimate_difficulty(kind="long_form", stem=stem, marks=Decimal("10"))
    assert big > small


def test_always_in_range():
    assert 1 <= estimate_difficulty(kind="mcq_single", stem="") <= 5
    assert estimate_difficulty(kind="long_form", stem="calculate " * 300, marks=20) <= 5
