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


def _table(rows: int) -> str:
    return "\n".join(f"| {y} | {y * 1000:,} |" for y in range(1, rows + 1))


def test_long_form_scores_spread_instead_of_saturating():
    theory = estimate_difficulty(
        kind="long_form", stem="Explain the concept of working capital with suitable examples.", marks=Decimal("7")
    )
    heavy = estimate_difficulty(
        kind="long_form",
        stem=(
            "A Ltd. has the following cash flows. Calculate NPV and IRR and advise on hedging with a forward contract.\n"
            "(a) Compute the NPV at 12%\n(b) Compute the IRR\n(c) Advise on the project\n" + _table(12)
        ),
        marks=Decimal("14"),
        solution="x = 1\n" * 50,
    )
    assert theory <= 2
    assert heavy >= 4
    assert heavy - theory >= 2


def test_seven_mark_computation_is_not_automatically_hardest():
    d = estimate_difficulty(
        kind="long_form",
        stem="Calculate the break-even point from the following: fixed cost 1,08,000 and contribution 80 per unit.",
        marks=Decimal("7"),
    )
    assert d <= 3


def test_calculation_mcq_is_harder_than_recall_mcq():
    recall = estimate_difficulty(
        kind="mcq_single", stem="Which section defines a subsidiary company?", options=["2(87)", "2(6)"]
    )
    calc = estimate_difficulty(
        kind="mcq_single",
        stem="EZAN Ltd. has an ROE of 18% and a ploughback ratio of 50%. Market capitalization rate is 13%. Earnings are 4 per share. Calculate the price in 3 years.",
        options=["75.10", "64.75", "60.50", "None of the above"],
    )
    assert calc > recall


def test_solution_length_sharpens_long_form():
    stem = "Prepare the statement and comment."
    short = estimate_difficulty(kind="long_form", stem=stem, marks=7, solution="Answer: 5")
    long = estimate_difficulty(kind="long_form", stem=stem, marks=7, solution="a = b\n" * 60)
    assert long > short
