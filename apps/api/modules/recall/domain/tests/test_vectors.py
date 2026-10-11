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


# ---------------------------------------------------------------- exam (R2-W1)
def _t(v):
    return None if v is None else datetime.fromisoformat(v.replace("Z", "+00:00"))


def test_the_exam_vectors_are_reproduced_by_the_domain():
    from modules.recall.domain import exam
    from modules.recall.domain.folding import ReviewEvent, effective_due, fold

    data = json.loads((VECTORS / "exam_cases.json").read_text())
    assert sum(len(v) for v in data.values()) >= 400
    for c in data["horizon"]:
        got = exam.horizon(
            _t(c["due"]), _t(c["last_review"]), _t(c["exam"]), c["card_id"], _t(c["now"]), enabled=c["enabled"]
        )
        assert got == _t(c["expected"]), c["name"]
    for c in data["retention"]:
        assert exam.retention_for(c["importance"], c["desired"], c["left"], enabled=c["enabled"]) == c["expected"]
    for c in data["r_exam"]:
        got = exam.r_exam(c["stability"], _t(c["last_review"]), _t(c["exam"]), c["w20"])
        assert got == c["expected"] if got is None else abs(got - c["expected"]) < 1e-12
    for c in data["quick"]:
        cards = [
            exam.QuickCard(x["id"], x["importance"], x["phase"], x["stability"], _t(x["last_review"]))
            for x in c["cards"]
        ]
        p = exam.quick_set(cards, _t(c["exam"]), c["minutes"], c["median"], _t(c["now"]), c["w20"])
        want = c["expected"]
        assert list(p.ids) == want["ids"] and p.candidates == want["candidates"] and p.cut_off == want["cut_off"], c[
            "name"
        ]
        assert (p.days_to_exam, p.window_days, p.per_day, p.minutes_per_day, p.too_few) == (
            want["days_to_exam"], want["window_days"], want["per_day"], want["minutes_per_day"], want["too_few"]
        )  # fmt: skip
    for c in data["cram"]:
        assert exam.cram_open(_t(c["now"]), _t(c["exam"])) is c["expected"]
    for c in data["pacing"]:
        p = exam.pacing(c["unseen"], c["days_left"], c["new_per_day"])
        want = c["expected"]
        assert (p.unseen, p.window_days, p.introduced_at_limit, p.needed_per_day, p.feasible) == (
            want["unseen"], want["window_days"], want["introduced_at_limit"], want["needed_per_day"], want["feasible"]
        )  # fmt: skip
    for c in data["fold_boost"]:
        cfg = fsrs6.Cfg(fuzz=True)
        events = [ReviewEvent(e["id"], _t(e["at"]), e["rating"]) for e in c["events"]]
        state = fold(
            events,
            list(fsrs6.DEFAULT_WEIGHTS),
            cfg,
            card_id=c["card_id"],
            cfg_for=lambda t, c=c, cfg=cfg: exam.cfg_at(cfg, c["importance"], t, _t(c["exam"])),
        )
        want = c["expected"]
        assert state.memory.stability == want["stability"] and state.memory.reps == want["reps"], c["name"]
        assert effective_due(state) == _t(want["effective_due"])
