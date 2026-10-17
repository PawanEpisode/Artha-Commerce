from modules.questionbank.domain.pdf_ingest import overrides as ov
from modules.questionbank.domain.pdf_ingest.cases import format_case_groups, shared_prefix
from modules.questionbank.domain.pdf_ingest.pyq import term_title
from modules.questionbank.domain.pdf_ingest.text import fix_pipeless_tables

CASE = (
    "Case Scenario:\nHighway Ltd. is a transport company providing transport to Government departments of three states. "
    "Each of the state governments hold 15% shares in the company and appointed an auditor.\nIn this context answer the following."
)


def _leaf(label, stem, parent="1"):
    return {
        "ref": label,
        "number_label": label,
        "kind": "mcq_single",
        "stem_md": stem,
        "parent_ref": parent,
        "is_leaf": True,
    }


def test_case_group_is_found_and_quoted():
    leaves = [_leaf(f"1({r})", f"{CASE}\n\nQuestion {r}?") for r in ("i", "ii", "iii")]
    assert format_case_groups(leaves) == ["1(i)", "1(ii)", "1(iii)"]
    first = leaves[0]["stem_md"]
    assert first.startswith("> **Case scenario** · questions (i) to (iii)")
    assert "Case Scenario:" not in first
    assert first.endswith("\n\nQuestion i?")
    assert leaves[2]["case_group"] == "1(i)-1(iii)"


def test_short_shared_opening_is_not_a_case():
    leaves = [_leaf("1(i)", "Choose the correct option:\n\nA?"), _leaf("1(ii)", "Choose the correct option:\n\nB?")]
    assert format_case_groups(leaves) == []
    assert leaves[0]["stem_md"].endswith("A?")


def test_unrelated_stems_and_other_parents_are_left_alone():
    leaves = [_leaf("1(i)", f"{CASE}\n\nQ?"), _leaf("2(i)", f"{CASE}\n\nQ?", parent="2")]
    assert format_case_groups(leaves) == []


def test_stem_that_is_only_the_shared_text_keeps_its_own_line():
    assert shared_prefix([f"{CASE}\n\nQ1?", CASE + "\n\nQ2?"]).endswith("answer the following.")
    assert shared_prefix([CASE, CASE + "\n\nQ2?"]) == ""


def test_pipeless_table_becomes_standard():
    out = fix_pipeless_tables("Intro\n Firm | Capital\n---|---\nA | 10\nB | 20\n\nAfter")
    assert "| Firm | Capital |\n|---|---|\n| A | 10 |\n| B | 20 |" in out
    assert out.startswith("Intro\n\n|")
    assert fix_pipeless_tables("| a | b |\n|---|---|\n| 1 | 2 |") == "| a | b |\n|---|---|\n| 1 | 2 |"


def test_title_does_not_repeat_the_paper():
    assert (
        term_title("20A", "Valuation (Elective Paper 20A)", "2023-12")
        == "CMA Final December 2023: Valuation (Paper 20A)"
    )


def test_overrides_apply_last_and_recompute_status():
    opts = [{"body_md": "x", "is_correct": False}, {"body_md": "y", "is_correct": False}]
    result = {
        "payload": {
            "answers_status": "none",
            "parts": [{"ref": "1(i)", "is_leaf": True, "kind": "long_form", "publish": False, "options": []}],
        },
        "report": [{"part": "1(i)", "reasons": ["x"]}, {"part": "2", "reasons": ["y"]}],
        "counts": {"draft_parts": 2},
    }
    fixed = [dict(opts[0], is_correct=True), opts[1]]
    assert ov.apply_overrides(result, {"1(i)": {"kind": "mcq_single", "options": fixed, "publish": True}}) == ["1(i)"]
    assert result["payload"]["answers_status"] == "complete"
    assert result["report"] == [{"part": "2", "reasons": ["y"]}]
    assert result["counts"]["draft_parts"] == 1


def _item(ref, stem, expl=""):
    return {
        "external_ref": ref,
        "status": "draft",
        "review_reasons": ["hold"],
        "payload": {"stem_md": stem, "explanation_md": expl, "rubric": {"reference_solution_md": expl}},
        "evidence": {"typeset_notes": []},
    }


def test_supplement_merge_and_insert_are_idempotent():
    from modules.questionbank.domain.pdf_ingest.supplement import apply_supplement

    items = [_item("a:q14", "Part one"), _item("a:q15", "Part two", "Solution")]
    sup = {
        "merge": [{"into": "a:q14", "from": "a:q15", "note": "owner"}],
        "insert": [{"after": "a:q14", "item": _item("a:q14b", "New")}],
    }
    assert len(apply_supplement(items, sup)) == 2
    assert [i["external_ref"] for i in items] == ["a:q14", "a:q14b"]
    assert items[0]["payload"]["stem_md"] == "Part one\n\nPart two"
    assert items[0]["payload"]["explanation_md"] == "Solution"
    assert items[0]["status"] == "ok" and items[0]["review_reasons"] == []
    assert apply_supplement(items, sup) == []
