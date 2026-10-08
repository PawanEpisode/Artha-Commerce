from __future__ import annotations

import pytest

from modules.recall.domain import cards


def codes(kind, fields):
    return {i.code for i in cards.validate(kind, fields)}


def test_every_kind_has_a_spec_and_renders():
    assert set(cards.KINDS) == set(cards.SPECS)
    samples = {
        "pointer": {"prompt_md": "Q", "answer_md": "A"},
        "formula": {"name": "Area", "expression_md": "$a b$", "when_md": "rectangles"},
        "section": {"act": "IT Act", "reference": "s 80C", "prompt_md": "Limit?", "gist_md": "1.5 lakh"},
        "definition": {"term": "Asset", "definition_md": "A resource", "source_ref": "AS 1"},
        "mnemonic": {"mnemonic": "FIFO", "expands_md": "First in first out"},
        "case_law": {"case_name": "A v B", "held_md": "Held X", "citation": "2020 SC 1", "year": "2020"},
        "cloze": {"text_md": "{{c1::Cash}} is {{c2::king::hint}}"},
    }
    for kind, fields in samples.items():
        assert cards.validate(kind, fields) == []
        front, back = cards.render(kind, fields, 1 if kind == "cloze" else 0)
        assert front and back


def test_required_fields_length_and_single_line():
    assert "required" in codes("pointer", {"prompt_md": " ", "answer_md": "A"})
    assert "too_long" in codes("pointer", {"prompt_md": "x" * 4001, "answer_md": "A"})
    assert "too_long" in codes("definition", {"term": "x" * 201, "definition_md": "d"})
    assert "single_line" in codes("definition", {"term": "a\nb", "definition_md": "d"})
    assert "unknown_field" in codes("pointer", {"prompt_md": "Q", "answer_md": "A", "x": "1"})
    assert "not_text" in codes("pointer", {"prompt_md": 3, "answer_md": "A"})
    assert codes("nope", {}) == {"unknown_kind"}


@pytest.mark.parametrize(
    ("text", "code"),
    [
        ("no deletion", "cloze_none"),
        ("{{c1::a}} {{c1::b}}", "cloze_duplicate"),
        ("{{c1::a}} {{c3::b}}", "cloze_gap"),
        (" ".join(f"{{{{c{i}::x}}}}" for i in range(1, 22)), "cloze_too_many"),
    ],
)
def test_cloze_rules(text, code):
    assert code in codes("cloze", {"text_md": text})


def test_cloze_faces_hide_only_their_own_deletion():
    fields = {"text_md": "{{c1::Cash}} is {{c2::king::hint}}"}
    assert cards.ordinals("cloze", fields) == [1, 2]
    assert cards.ordinals("pointer", {}) == [0]
    assert cards.render("cloze", fields, 1) == ("[...] is king", "**Cash** is king")
    assert cards.render("cloze", fields, 2) == ("Cash is [hint]", "Cash is **king**")


def test_suggest_kind():
    assert cards.suggest_kind("Kesavananda Bharati v. State of Kerala, Supreme Court, 1973")[0] == "case_law"
    assert cards.suggest_kind("Section 80C allows a deduction")[0] == "section"
    assert cards.suggest_kind("Profit = Revenue - Cost")[0] == "formula"
    assert cards.suggest_kind("A lease means a transfer of a right")[0] == "definition"
    assert cards.suggest_kind("Some plain sentence.") == ("pointer", 0.3)


def test_fingerprint_ignores_case_whitespace_and_dollars():
    a = cards.fingerprint("pointer", {"prompt_md": "What is $x$?", "answer_md": "Ten"})
    b = cards.fingerprint("pointer", {"prompt_md": "what  is x?", "answer_md": " ten "})
    c = cards.fingerprint("pointer", {"prompt_md": "What is y?", "answer_md": "Ten"})
    assert a == b != c
