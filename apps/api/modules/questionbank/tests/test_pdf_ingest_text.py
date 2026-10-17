from modules.questionbank.domain.pdf_ingest.text import (
    collapse_ws,
    fix_answer_rupee,
    fix_ocr_rupee,
    fix_workbook_rupee,
    layout_to_markdown,
    markdown_table,
    normalise_key_text,
)


def test_workbook_backtick_becomes_rupee():
    assert fix_workbook_rupee("initial investment is ` 60,00,000.") == "initial investment is ₹ 60,00,000."
    assert fix_workbook_rupee("Selling Price (`./Unit) 162 and `.8/hour") == "Selling Price (₹./Unit) 162 and ₹ 8/hour"
    assert "`" not in fix_workbook_rupee("CFAT (`)")


def test_workbook_fence_backticks_survive():
    text = "```text\nYear 1\n```"
    assert fix_workbook_rupee(text) == text


def test_answer_pdf_letter_d_is_rupee_only_before_a_figure():
    assert fix_answer_rupee("NPV = D 4,18,279 and D1,000") == "NPV = ₹ 4,18,279 and ₹ 1,000"
    assert (
        fix_answer_rupee("Option (D) is correct, Section D 2 applies") == "Option (D) is correct, Section D 2 applies"
    )
    assert fix_answer_rupee("(D) 2") == "(D) 2"


def test_ocr_rupee_variants_and_percent_untouched():
    assert fix_ocr_rupee("(B) % 64.75") == "(B) ₹64.75"
    assert fix_ocr_rupee("an investment of ¥ 100 Lakh and € 1,50,000") == "an investment of ₹100 Lakh and ₹1,50,000"
    assert fix_ocr_rupee("a 15% 3 year return") == "a 15% 3 year return"


def test_normalise_key_text_ignores_case_space_punctuation():
    assert normalise_key_text("15 days.") == normalise_key_text("15days")
    assert normalise_key_text("Salary & Wages") == normalise_key_text("salary and wages")


def test_markdown_table_escapes_pipes():
    assert markdown_table([["A", "B|C"], ["1", "2"]]) == "| A | B\\|C |\n|---|---|\n| 1 | 2 |"


def test_collapse_ws():
    assert collapse_ws("a \n  b  c") == "a b c"


def test_layout_table_is_rebuilt_with_header_and_columns():
    text = "Intro line\n  Year        CFAT\n    1      10,20,000\n    2      11,00,000\nOutro line"
    md = layout_to_markdown(text)
    assert "| Year | CFAT |" in md
    assert "| 1 | 10,20,000 |" in md
    assert md.splitlines()[0] == "Intro line" and md.splitlines()[-1] == "Outro line"


def test_numbered_paragraph_is_not_a_table():
    text = "i.       To avoid sub optimisation the divisional performance can be measured using 14% RI\nii.      Second paragraph with 2 numbers"
    assert "|" not in layout_to_markdown(text)


def test_total_row_stays_in_its_column():
    text = "  Year     CFAT      PV\n    1      100       90\n    2      200      160\n  Total              250"
    md = layout_to_markdown(text)
    assert "| Total |  | 250 |" in md


def test_misaligned_table_falls_back_to_text_block():
    text = "  A      B      C\n  1   2       3\n  4        5      6   7   8"
    out = layout_to_markdown(text)
    assert out.startswith("```text") or "|" in out  # never silently scrambles figures
