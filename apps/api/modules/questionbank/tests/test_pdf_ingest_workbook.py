from decimal import Decimal

from modules.questionbank.domain.pdf_ingest.seedbuild import single_numeric_answer
from modules.questionbank.domain.pdf_ingest.workbook import DEFAULT_MARKS, parse_workbook


def _pages(*texts):
    return [{"page": i + 1, "blocks": [{"type": "text", "text": t}]} for i, t in enumerate(texts)]


PAGE1 = """
                     Work Book : Strategic Financial Management

        1
                         Investment Decisions, Project
                             Planning and Control
                            [Study Material - Module 1]

Illustration 1
NTPC is going to start a project. Initial investment is ` 60,00,000.
  Year        CFAT
    1      10,20,000
    2      11,00,000
Compute the NPV.
Solution:
NPV = ` (58,72,207 - 60,00,000) = (` 1,27,793)
Directorate of Studies, The Institute of Cost Accountants of India (Statutory Body under an Act of Parliament)   1
"""
PAGE2 = """
                     Work Book : Strategic Financial Management
Illustration 2
CESC supplies the following data to determine NPV of the project to be set up at Sonarpur.
Solution:
Since inflation rate is 10% p.a., real cash flows are converted into nominal cash flows.

        2
                         Evaluation of Risky Proposal
                            [Study Material - Module 2]

ILLUSTRATION 1
Second chapter question with enough words to count as a stem here.
Answer: Final result is 42
"""


def test_items_chapters_and_marks():
    items, problems = parse_workbook(_pages(PAGE1, PAGE2))
    assert problems == []
    assert [(i.chapter_index, i.ordinal) for i in items] == [(1, 1), (1, 2), (2, 1)]
    assert items[0].chapter_title == "Investment Decisions, Project Planning and Control"
    assert items[2].chapter_title == "Evaluation of Risky Proposal"
    assert all(i.marks == DEFAULT_MARKS == Decimal("7") and i.marks_source == "inferred" for i in items)


def test_stem_has_markdown_table_and_rupee_and_footer_removed():
    items, _ = parse_workbook(_pages(PAGE1, PAGE2))
    assert "| Year | CFAT |" in items[0].stem_md
    assert "₹ 60,00,000" in items[0].stem_md
    assert "Directorate of Studies" not in items[0].solution_md
    assert "₹ (58,72,207" in items[0].solution_md


def test_next_chapter_title_is_not_glued_to_previous_solution():
    items, _ = parse_workbook(_pages(PAGE1, PAGE2))
    assert "Evaluation of Risky" not in items[1].solution_md
    assert not items[1].solution_md.rstrip().endswith("2")


def test_missing_solution_marker_is_flagged():
    page = "[Study Material - Module 1]\nIllustration 1\nA question without any marker but with a lot of words in it.\n"
    items, _ = parse_workbook(_pages(page))
    assert items[0].status == "needs_review"
    assert "no 'Solution:'" in items[0].review_reasons[0]


def test_large_image_flags_item_small_logo_does_not():
    pages = _pages(
        "[Study Material - Module 1]\nIllustration 1\nA question about the diagram shown here in the page.\nSolution:\nSee working below it."
    )
    pages[0]["blocks"].append({"type": "image", "w": 300, "h": 200})
    pages[0]["blocks"].append({"type": "image", "w": 20, "h": 20})
    items, _ = parse_workbook(pages)
    assert len(items[0].review_reasons) == 1 and "picture" in items[0].review_reasons[0]


def test_numeric_key_only_for_a_single_ask_ending_in_one_figure():
    assert single_numeric_answer("Calculate the break-even point.", "BEP = 1,350 units")["numeric_value"] == "1350"
    assert single_numeric_answer("Calculate NPV and comment on the project.", "NPV = 5") is None
    assert single_numeric_answer("Compute:\n(a) NPV\n(b) IRR", "NPV = 5") is None
    assert single_numeric_answer("Calculate the price.", "The price is high") is None
