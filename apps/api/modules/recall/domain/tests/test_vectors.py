"""Golden vectors: the Python domain must reproduce them, and so must the TypeScript twin (same files, same tolerance)."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest

from modules.recall.domain import fsrs6
from modules.recall.domain.folding import ReviewEvent, ScheduleEvent, effective_due, fold
from modules.recall.domain.scheduling import CardView, Limits, plan_queue

VECTORS = Path(__file__).parent / "vectors"
TOL = 1e-9


def load(name: str) -> dict:
    return json.loads((VECTORS / name).read_text(encoding="utf-8"))


def ts(value: str | None) -> datetime | None:
    return None if value is None else datetime.fromisoformat(value.replace("Z", "+00:00"))


def cfg_of(d: dict) -> fsrs6.Cfg:
    return fsrs6.Cfg(
        d["desired_retention"],
        tuple(d["learning_steps"]),
        tuple(d["relearning_steps"]),
        d["max_interval_days"],
        d["fuzz"],
    )


def close(a: float | None, b: float | None) -> bool:
    return a is None and b is None or (a is not None and b is not None and abs(a - b) <= TOL * max(1.0, abs(b)))


def assert_state(got: fsrs6.MemoryState, want: dict) -> None:
    assert got.phase == want["phase"]
    assert got.step == want["step"]
    assert close(got.stability, want["stability"])
    assert close(got.difficulty, want["difficulty"])
    assert got.last_review_at == ts(want["last_review_at"])
    assert (got.reps, got.lapses) == (want["reps"], want["lapses"])
    assert got.last_lapse_at == ts(want["last_lapse_at"])


FS = load("fsrs6_cases.json")


def test_vectors_carry_the_scheduler_version():
    assert FS["scheduler_version"] == fsrs6.SCHEDULER_VERSION == "fsrs-6.0"
    assert len(FS["cases"]) >= 40


@pytest.mark.parametrize("case", FS["cases"], ids=lambda c: c["name"])
def test_fsrs6_history(case):
    cfg, state = cfg_of(case["cfg"]), fsrs6.MemoryState()
    for step in case["steps"]:
        out = fsrs6.review(state, step["rating"], ts(step["at"]), case["weights"], cfg, card_id=case["card_id"])
        state = out.state
        assert_state(state, step["state"])
        assert close(out.scheduled_days, step["scheduled_days"])
        assert out.due_at == ts(step["due_at"]) or abs((out.due_at - ts(step["due_at"])).total_seconds()) < 1e-3
        assert out.elapsed_days == step["elapsed_days"]
        assert close(out.retrievability_before, step["retrievability_before"])
        assert out.lapsed == step["lapsed"]


@pytest.mark.parametrize(("days", "label"), FS["format_interval"])
def test_format_interval(days, label):
    assert fsrs6.format_interval(days) == label


@pytest.mark.parametrize(("card_id", "reps", "unit"), FS["fuzz_unit"])
def test_fuzz_unit(card_id, reps, unit):
    assert fsrs6.fuzz_unit(card_id, reps) == unit


FO = load("folding_cases.json")


def event_of(e: dict):
    if e["type"] == "review":
        return ReviewEvent(e["id"], ts(e["at"]), e["rating"], e["counts"], e["voided"])
    return ScheduleEvent(e["id"], ts(e["at"]), e["kind"], ts(e["to_due"]), e["cap_days"])


@pytest.mark.parametrize("case", FO["cases"], ids=lambda c: c["name"])
def test_folding(case):
    state = fold(
        [event_of(e) for e in case["events"]], fsrs6.DEFAULT_WEIGHTS, cfg_of(case["cfg"]), card_id=case["card_id"]
    )
    want = case["expected"]
    assert_state(state.memory, want["memory"])
    assert state.due_scheduled_at == ts(want["due_scheduled_at"])
    assert state.postponed_until == ts(want["postponed_until"])
    assert effective_due(state) == ts(want["effective_due"])


QU = load("queue_cases.json")


@pytest.mark.parametrize("case", QU["cases"], ids=lambda c: c["name"])
def test_queue(case):
    cards = [
        CardView(
            c["id"],
            c["subject"],
            c["importance"],
            c["phase"],
            c["stability"],
            ts(c["last_review_at"]),
            ts(c["due_at"]),
            ts(c["created_at"]),
        )
        for c in case["cards"]
    ]
    q = plan_queue(
        cards, ts(case["now"]), Limits(**case["limits"]), case["w20"], mode=case["mode"], day_end=ts(case["day_end"])
    )
    want = case["expected"]
    assert list(q.ids) == want["ids"]
    assert (q.learning, q.reviews, q.new) == (want["learning"], want["reviews"], want["new"])
    assert q.catchup.__dict__ == want["catchup"]
