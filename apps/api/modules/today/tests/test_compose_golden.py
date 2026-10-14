"""The PRD 5.6 worked example, byte for byte on keys and order (FR-F13-03, FR-F13-10)."""

import json
from datetime import date
from pathlib import Path

import pytest

from modules.today.domain import compose as cp

FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "golden_5_6.json").read_text())


def build_context(raw: dict, **over) -> cp.Context:
    fields = dict(
        local_date=date.fromisoformat(raw["local_date"]),
        phase=raw["phase"],
        days_to_exam=raw["days_to_exam"],
        budget_minutes=raw["budget_minutes"],
        focus_papers=raw["focus_papers"],
        max_tasks=raw["max_tasks"],
        seed=raw["seed"],
        papers=tuple(cp.PaperInfo(p["key"], p["days_untouched"]) for p in raw["papers"]),
    )
    fields.update(over)
    return cp.Context(**fields)


def build_candidate(row: dict, **over) -> cp.Candidate:
    fields = dict(
        provider="test.fixture",
        kind=row["slot"] + "_task",
        group=row["group"],
        slot=row["slot"],
        dedupe_key=row["id"],
        title=row["title"],
        reason_code="custom",
        reason="because",
        link_path="/app/revision",
        est_minutes=row["min"],
        urgency=row["u"],
        importance=row["i"],
        weakness=row["w"],
        freshness=row["f"],
        paper_key=row["paper"],
    )
    fields.update(over)
    return cp.Candidate(**fields)


@pytest.fixture
def selection():
    ctx = build_context(FIXTURE["context"])
    return cp.compose([build_candidate(r) for r in FIXTURE["candidates"]], ctx)


def test_scores_match_the_prd_table(selection):
    by_key = {p.candidate.dedupe_key: p.score for p in selection.picks}
    expected = {r["id"]: r["score"] for r in FIXTURE["candidates"]}
    assert all(by_key[k] == expected[k] for k in by_key)
    assert len(by_key) == 6


def test_selection_follows_the_rounds_of_the_worked_example(selection):
    exp = FIXTURE["expected"]
    by_rank = sorted(selection.picks, key=lambda p: p.rank)
    assert [p.candidate.dedupe_key for p in by_rank] == exp["selection_order"]


def test_display_order_tiles_and_starter(selection):
    exp = FIXTURE["expected"]
    assert selection.keys() == exp["display_order"]
    assert [(t.paper_key, [p.candidate.dedupe_key for p in t.picks]) for t in selection.tiles] == [
        (key, keys) for key, keys in exp["tiles"]
    ]
    assert selection.starter.candidate.dedupe_key == exp["starter"]
    assert [p.position for p in selection.picks] == list(range(6))


def test_budget_and_focus_papers(selection):
    exp = FIXTURE["expected"]
    assert selection.planned_minutes == exp["planned_minutes"] == 61
    assert selection.planned_minutes <= 81  # 125 percent of 65
    assert selection.focus == tuple(exp["focus"])
    assert selection.starved == tuple(exp["starved"])


def test_paper_need_numbers_of_the_worked_example(selection):
    needs = {t.paper_key: t.need for t in selection.tiles}
    assert needs["taxation"] == FIXTURE["expected"]["needs"]["taxation"]
    assert needs["costing"] == FIXTURE["expected"]["needs"]["costing"]
    # Audit waits until tomorrow: its need (1116) is below both focus papers.
    assert "audit" not in needs
    assert FIXTURE["expected"]["needs"]["audit"] < needs["costing"]


def test_selection_log_counts_what_was_left_out(selection):
    log = selection.selection_log()
    assert log["v"] == 1 and log["candidates"] == 9
    assert log["focus_papers"] == ["taxation", "costing"] and log["starved"] == ["costing"]
    assert log["dropped"]["not_focus"] == 2  # both Audit candidates
    assert log["dropped"]["budget"] == 1  # I (40 minutes) never fit
    assert sum(log["dropped"].values()) == 3


def test_every_task_explains_itself(selection):
    costing = next(p for p in selection.picks if p.candidate.dedupe_key == "F")
    b = costing.breakdown
    assert b["signals"] == {"u": 50, "i": 60, "w": 70, "f": 95}
    assert b["base"] == 642 and b["phase_mult"] == 120 and b["rank"] == 2
    assert b["modifiers"] == ["exam_in_60_days", "starved_paper"]
    taxation = next(p for p in selection.picks if p.candidate.dedupe_key == "A")
    assert taxation.breakdown["modifiers"] == ["exam_in_60_days"]


def test_same_inputs_give_the_same_plan():
    ctx = build_context(FIXTURE["context"])
    rows = [build_candidate(r) for r in FIXTURE["candidates"]]
    first = cp.compose(rows, ctx)
    again = cp.compose(list(reversed(rows)), ctx)  # input order must not matter
    assert first.keys() == again.keys()
    assert [p.breakdown for p in first.picks] == [p.breakdown for p in again.picks]
