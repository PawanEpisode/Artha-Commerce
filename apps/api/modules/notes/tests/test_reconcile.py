"""Field-level compare-and-set (ERD 3.6), shared with `reconcile.test.ts` through `reconcile_cases.json`."""

import json
from pathlib import Path

import pytest

from modules.notes.domain import merge

FIXTURES = json.loads((Path(__file__).parent / "fixtures" / "reconcile_cases.json").read_text())


@pytest.mark.parametrize("case", FIXTURES["reconcile"], ids=lambda c: c["name"])
def test_reconcile_fields(case):
    assert merge.reconcile_fields(case["stored"], case["base"], case["incoming"]) == case["expected"]


@pytest.mark.parametrize("case", FIXTURES["merge3"], ids=lambda c: c["name"])
def test_merge3_stable(case):
    result = merge.merge3_stable(case["base"], case["mine"], case["theirs"])
    assert (result.text, result.clean) == (case["text"], case["clean"])


@pytest.mark.parametrize("case", FIXTURES["resolve"], ids=lambda c: c["name"])
def test_resolve_conflict(case):
    assert merge.resolve_conflict(case["resolution"], case["mine"], case["theirs"]) == case["expected"]


@pytest.mark.parametrize("case", FIXTURES["edit_vs_delete"], ids=lambda c: c["name"])
def test_resolve_edit_vs_delete(case):
    got = merge.resolve_edit_vs_delete(
        stored_deleted=case["stored_deleted"], stored_rev=case["stored_rev"], base_rev=case["base_rev"], op=case["op"]
    )
    assert got == case["expected"]


def test_edit_wins_over_delete_in_every_order():
    live_edited = merge.resolve_edit_vs_delete(stored_deleted=False, stored_rev=5, base_rev=3, op="delete")
    assert live_edited == {"action": "keep", "restored": False}
    tombstone = merge.resolve_edit_vs_delete(stored_deleted=True, stored_rev=4, base_rev=3, op="edit")
    assert tombstone == {"action": "restore", "restored": True}
    assert merge.resolve_edit_vs_delete(stored_deleted=True, stored_rev=4, base_rev=3, op="delete")["action"] == "noop"


def test_bad_arguments_are_programming_errors():
    with pytest.raises(ValueError):
        merge.resolve_conflict("neither", "a", "b")
    with pytest.raises(ValueError):
        merge.resolve_edit_vs_delete(stored_deleted=False, stored_rev=1, base_rev=1, op="move")
    with pytest.raises(ValueError):
        merge.reconcile_fields({}, {}, {}, text_fields=("x",), geometry_fields=("x",))


def test_custom_text_fields_are_merged_like_comments():
    base = {"body": "alpha beta gamma"}
    result = merge.reconcile_fields(
        {"body": "ALPHA beta gamma"}, base, {"body": "alpha beta GAMMA"}, text_fields=("body",)
    )
    assert result["accepted"] == {"body": "ALPHA beta GAMMA"} and result["conflict"] is None
