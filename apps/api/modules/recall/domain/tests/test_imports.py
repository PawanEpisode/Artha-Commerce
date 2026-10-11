"""The pure import parser (R2-W3 F)."""

from __future__ import annotations

from modules.recall.domain import imports as imp


def test_plain_lines_are_one_pointer_each_and_blank_lines_are_skipped():
    rows = imp.parse_text("Sec 16 :: standard deduction\n\n  Sec 80C :: 1.5 lakh  \n")
    assert [(r.line, r.kind, r.front, r.back, r.error) for r in rows] == [
        (1, "pointer", "Sec 16", "standard deduction", None),
        (3, "pointer", "Sec 80C", "1.5 lakh", None),
    ]


def test_a_plain_line_without_a_back_is_an_error_row_not_a_card():
    (row,) = imp.parse_text("only a question")
    assert row.error == imp.MISSING_BACK and row.front == "only a question"


def test_a_tab_also_splits_front_and_back():
    (row,) = imp.parse_text("front\tback")
    assert (row.front, row.back) == ("front", "back")


def test_the_header_switches_to_columns_in_any_delimiter():
    for d in (",", "\t", ";"):
        text = f"kind{d}front{d}back{d}chapter\nformula{d}Q{d}A{d}ch-1\n"
        (row,) = imp.parse_text(text)
        assert (row.line, row.kind, row.front, row.back, row.chapter) == (2, "formula", "Q", "A", "ch-1")


def test_the_chapter_column_is_optional_and_a_blank_kind_is_a_pointer():
    (row,) = imp.parse_text("kind,front,back\n,Q,A")
    assert (row.kind, row.chapter) == ("pointer", "")


def test_quoted_cells_hold_commas_and_line_breaks_and_lines_stay_true():
    rows = imp.parse_text('kind,front,back,chapter\npointer,"a, b","line1\nline2",\ndefinition,T,D,\n')
    assert rows[0].front == "a, b" and rows[0].back == "line1\nline2" and rows[0].line == 2
    assert rows[1].line == 4  # the quoted break took a physical line


def test_too_many_columns_is_an_error_row():
    (row,) = imp.parse_text("kind,front,back,chapter\na,b,c,d,e")
    assert row.error == imp.TOO_MANY_COLUMNS


def test_empty_and_windows_line_endings():
    assert imp.parse_text("") == [] and imp.parse_text("\n \n") == []
    assert len(imp.parse_text("a :: b\r\nc :: d\r\n")) == 2


def test_structured_rows_number_from_one_and_trim():
    rows = imp.from_rows(
        [{"front": " Q ", "back": "A"}, {"kind": "Formula", "front": "N", "back": "E", "chapter": "x"}]
    )
    assert [(r.line, r.kind, r.front) for r in rows] == [(1, "pointer", "Q"), (2, "formula", "N")]


def test_front_and_back_map_to_the_first_two_required_fields():
    assert (
        imp.importable_fields(["a", "b"])
        and imp.importable_fields(["a"])
        and not imp.importable_fields(["a", "b", "c"])
    )
    row = imp.RawRow(1, "pointer", "F", "B")
    assert imp.map_fields(["prompt_md", "answer_md"], row) == {"prompt_md": "F", "answer_md": "B"}
    assert imp.map_fields(["text_md"], row) == {"text_md": "F"}
