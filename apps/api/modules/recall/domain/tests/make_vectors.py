"""
Regenerates the golden vectors in `vectors/`. The TypeScript twin (`apps/web/src/modules/recall/lib`) must reproduce them.

    cd apps/api && PYTHONPATH=/path/to/fsrs python -m modules.recall.domain.tests.make_vectors

Fuzz-off rows are cross-checked against py-fsrs while generating (needs `fsrs`); fuzz-on rows come from our own code, since
the fuzz is ours (D6). Review the diff of the JSON files in the pull request: a change here is a change of behaviour.
"""

from __future__ import annotations

import json
import random
from datetime import UTC, datetime, timedelta
from pathlib import Path

from modules.recall.domain import fsrs6
from modules.recall.domain.folding import CardState, ReviewEvent, ScheduleEvent, effective_due, fold
from modules.recall.domain.scheduling import CardView, Limits, plan_queue

OUT = Path(__file__).parent / "vectors"
T0 = datetime(2026, 3, 2, 8, 0, tzinfo=UTC)
W = list(fsrs6.DEFAULT_WEIGHTS)
W_ALT = [*W[:20], 0.3]  # a flatter forgetting curve


def iso(t: datetime) -> str:
    return t.isoformat().replace("+00:00", "Z")


def cfg_json(c: fsrs6.Cfg) -> dict:
    return {
        "desired_retention": c.desired_retention,
        "learning_steps": list(c.learning_steps),
        "relearning_steps": list(c.relearning_steps),
        "max_interval_days": c.max_interval_days,
        "fuzz": c.fuzz,
    }


def state_json(s: fsrs6.MemoryState) -> dict:
    return {
        "phase": s.phase,
        "step": s.step,
        "stability": s.stability,
        "difficulty": s.difficulty,
        "last_review_at": iso(s.last_review_at) if s.last_review_at else None,
        "reps": s.reps,
        "lapses": s.lapses,
        "last_lapse_at": iso(s.last_lapse_at) if s.last_lapse_at else None,
    }


def run(cfg: fsrs6.Cfg, weights: list[float], card_id: str, history: list[tuple[int, int]]) -> dict:
    """history: (minutes since previous review, rating)."""
    state, t, steps = fsrs6.MemoryState(), T0, []
    for minutes, rating in history:
        t = t + timedelta(minutes=minutes)
        out = fsrs6.review(state, rating, t, weights, cfg, card_id=card_id)
        state = out.state
        steps.append(
            {
                "at": iso(t),
                "rating": rating,
                "state": state_json(state),
                "scheduled_days": out.scheduled_days,
                "due_at": iso(out.due_at),
                "elapsed_days": out.elapsed_days,
                "retrievability_before": out.retrievability_before,
                "lapsed": out.lapsed,
            }
        )
    return {"cfg": cfg_json(cfg), "weights": weights, "card_id": card_id, "steps": steps}


def oracle_check(case: dict) -> None:
    try:
        from fsrs import Card, Rating, Scheduler
    except ImportError:  # pragma: no cover
        return
    c = case["cfg"]
    if c["fuzz"] or case["weights"] != W:
        return
    sch = Scheduler(
        desired_retention=c["desired_retention"],
        learning_steps=tuple(timedelta(minutes=m) for m in c["learning_steps"]),
        relearning_steps=tuple(timedelta(minutes=m) for m in c["relearning_steps"]),
        maximum_interval=c["max_interval_days"],
        enable_fuzzing=False,
    )
    card = Card()
    for step in case["steps"]:
        at = datetime.fromisoformat(step["at"].replace("Z", "+00:00"))
        card, _ = sch.review_card(card, Rating(step["rating"]), at)
        assert abs(card.stability - step["state"]["stability"]) < 1e-6, case["name"]
        assert abs((card.due - datetime.fromisoformat(step["due_at"].replace("Z", "+00:00"))).total_seconds()) < 1


def fsrs_cases() -> dict:
    cases = []
    base = fsrs6.Cfg(fuzz=False)
    scripts = {
        "good_x6": [(0, 3)] + [(1, 3), (10, 3)] + [(1440 * d, 3) for d in (1, 3, 8, 20)],
        "easy_first": [(0, 4), (1440, 3), (4000, 3)],
        "again_first_then_good": [(0, 1), (1, 3), (10, 3), (10, 3), (1440 * 2, 3)],
        "hard_first": [(0, 2), (6, 2), (10, 3), (1440, 3)],
        "lapse_and_relearn": [(0, 3), (1, 3), (10, 3), (1440, 3), (1440 * 4, 1), (10, 3), (1440, 3)],
        "double_lapse": [(0, 4), (1440 * 2, 1), (10, 1), (10, 3), (30, 3), (1440, 3)],
        "same_day_review_phase": [(0, 3), (1, 3), (10, 3), (1440, 3), (60, 3), (120, 2), (30, 4)],
        "overdue_by_months": [(0, 3), (1, 3), (10, 3), (1440 * 200, 3), (1440 * 400, 3)],
        "hard_in_review": [(0, 3), (1, 3), (10, 3), (1440, 2), (1440 * 3, 2), (1440 * 6, 3)],
        "all_easy": [(0, 4), (1440 * 5, 4), (1440 * 40, 4), (1440 * 200, 4)],
    }
    variants = {
        "default": base,
        "no_steps": fsrs6.Cfg(0.90, (), (), 365, False),
        "long_steps": fsrs6.Cfg(0.90, (5, 15, 60), (10, 30), 365, False),
        "high_retention": fsrs6.Cfg(0.95, (1, 10), (10,), 365, False),
        "low_retention": fsrs6.Cfg(0.82, (1, 10), (10,), 365, False),
        "max_interval_60": fsrs6.Cfg(0.90, (1, 10), (10,), 60, False),
    }
    for sname, hist in scripts.items():
        for vname, cfg in variants.items():
            if vname != "default" and sname not in ("good_x6", "lapse_and_relearn", "all_easy"):
                continue
            cases.append({"name": f"{sname}:{vname}", **run(cfg, W, "card-1", hist)})
    cases.append({"name": "good_x6:alt_weights", **run(base, W_ALT, "card-1", scripts["good_x6"])})
    cases.append({"name": "lapse_and_relearn:alt_weights", **run(base, W_ALT, "card-1", scripts["lapse_and_relearn"])})
    for i, cid in enumerate(("card-1", "0b1f2a9c-7a55-4a65-8a33-2f3a9b1c0d11", "c" * 36)):
        fz = fsrs6.Cfg(fuzz=True)
        cases.append({"name": f"fuzz_good_x6:{i}", **run(fz, W, cid, scripts["good_x6"])})
        cases.append({"name": f"fuzz_overdue:{i}", **run(fz, W, cid, scripts["overdue_by_months"])})
    rnd = random.Random(20261009)
    for i in range(8):
        hist = [(0, rnd.choice([1, 2, 3, 3, 4]))]
        for _ in range(rnd.randint(4, 14)):
            hist.append((rnd.choice([1, 10, 90, 1440, 4320, 20000, 90000]), rnd.choice([1, 2, 3, 3, 3, 4])))
        cases.append({"name": f"random:{i}", **run(fsrs6.Cfg(fuzz=False), W, "r", hist)})
        cases.append({"name": f"random_fuzz:{i}", **run(fsrs6.Cfg(fuzz=True), W, f"r-{i}", hist)})
    for case in cases:
        oracle_check(case)
    fmt = [
        [d, fsrs6.format_interval(d)]
        for d in (
            0.0,
            1 / 1440,
            5 / 1440,
            59 / 1440,
            1 / 24,
            3 / 24,
            23 / 24,
            1.0,
            1.4,
            1.5,
            2.5,
            5.0,
            30.0,
            30.5,
            31.0,
            45.0,
            90.0,
            364.0,
            365.0,
            548.0,
            730.0,
            3650.0,
        )
    ]
    fuzz = [
        [cid, reps, fsrs6.fuzz_unit(cid, reps)]
        for cid in ("", "a", "card-1", "0b1f2a9c-7a55-4a65-8a33-2f3a9b1c0d11")
        for reps in (0, 1, 2, 17, 4000)
    ]
    return {"scheduler_version": fsrs6.SCHEDULER_VERSION, "cases": cases, "format_interval": fmt, "fuzz_unit": fuzz}


def folding_cases() -> dict:
    cfg = fsrs6.Cfg(fuzz=True)
    out = []

    def add(name: str, events: list) -> None:
        state: CardState = fold(events, W, cfg, card_id="card-f")
        due = effective_due(state)
        out.append(
            {
                "name": name,
                "cfg": cfg_json(cfg),
                "card_id": "card-f",
                "events": [
                    (
                        {
                            "type": "review",
                            "id": e.id,
                            "at": iso(e.at),
                            "rating": e.rating,
                            "counts": e.counts_for_scheduling,
                            "voided": e.voided,
                        }
                        if isinstance(e, ReviewEvent)
                        else {
                            "type": "schedule",
                            "id": e.id,
                            "at": iso(e.at),
                            "kind": e.kind,
                            "to_due": iso(e.to_due) if e.to_due else None,
                            "cap_days": e.cap_days,
                        }
                    )
                    for e in events
                ],
                "expected": {
                    "memory": state_json(state.memory),
                    "due_scheduled_at": iso(state.due_scheduled_at) if state.due_scheduled_at else None,
                    "postponed_until": iso(state.postponed_until) if state.postponed_until else None,
                    "effective_due": iso(due) if due else None,
                },
            }
        )

    def r(i: str, minutes: int, rating: int, **kw) -> ReviewEvent:
        return ReviewEvent(i, T0 + timedelta(minutes=minutes), rating, **kw)

    def s(i: str, minutes: int, kind: str, **kw) -> ScheduleEvent:
        return ScheduleEvent(i, T0 + timedelta(minutes=minutes), kind, **kw)

    day = 1440
    base = [r("r1", 0, 3), r("r2", 1, 3), r("r3", 11, 3), r("r4", day, 3), r("r5", 4 * day, 3)]
    add("empty", [])
    add("plain", base)
    add("shuffled_with_duplicates", [base[3], base[0], base[0], base[4], base[1], base[2], base[3]])
    add("voided_review_is_skipped", [*base[:4], r("r5", 4 * day, 1, voided=True)])
    add("not_counted_review_is_skipped", [*base[:4], r("r5", 4 * day, 1, counts_for_scheduling=False)])
    add("forget_in_the_middle", [*base[:3], s("s1", 12 * 60, "forget"), r("r6", day, 4)])
    add(
        "content_reset_caps_stability",
        [*base[:4], s("s1", 6 * day, "content_reset", cap_days=3.0), r("r7", 7 * day, 3)],
    )
    add(
        "postpone_then_review_clears",
        [*base[:4], s("s1", 2 * day, "postpone", to_due=T0 + timedelta(days=20)), r("r8", 10 * day, 3)],
    )
    add("postpone_only", [*base[:4], s("s1", 2 * day, "postpone", to_due=T0 + timedelta(days=20))])
    add(
        "unpostpone",
        [*base[:4], s("s1", 2 * day, "postpone", to_due=T0 + timedelta(days=20)), s("s2", 3 * day, "unpostpone")],
    )
    add("same_instant_reset_before_review", [*base[:3], s("s1", day, "content_reset", cap_days=1.0), r("r9", day, 3)])
    add("audit_only_kind_ignored", [*base[:3], s("s1", day, "rebalance_note")])
    return {"scheduler_version": fsrs6.SCHEDULER_VERSION, "cases": out}


def queue_cases() -> dict:
    now = datetime(2026, 3, 20, 9, 0, tzinfo=UTC)
    w20 = W[20]

    def card(i: str, subj: str, imp: int, phase: int, stab, last_days, due_days) -> CardView:
        return CardView(
            id=i,
            subject=subj,
            importance=imp,
            phase=phase,
            stability=stab,
            last_review_at=None if last_days is None else now - timedelta(days=last_days),
            due_at=None if due_days is None else now + timedelta(days=due_days),
            created_at=now - timedelta(days=30) + timedelta(minutes=len(i)),
        )

    def view_json(c: CardView) -> dict:
        return {
            "id": c.id, "subject": c.subject, "importance": c.importance, "phase": c.phase, "stability": c.stability,
            "last_review_at": iso(c.last_review_at) if c.last_review_at else None,
            "due_at": iso(c.due_at) if c.due_at else None, "created_at": iso(c.created_at) if c.created_at else None,
        }  # fmt: skip

    cases = []

    def add(name: str, cards: list[CardView], limits: Limits, mode: str = "auto", day_end=None) -> None:
        q = plan_queue(cards, now, limits, w20, mode=mode, day_end=day_end)
        cases.append(
            {
                "name": name,
                "now": iso(now),
                "w20": w20,
                "mode": mode,
                "day_end": iso(day_end) if day_end else None,
                "limits": limits.__dict__,
                "cards": [view_json(c) for c in cards],
                "expected": {"ids": list(q.ids), "learning": q.learning, "reviews": q.reviews, "new": q.new,
                             "catchup": q.catchup.__dict__},
            }
        )  # fmt: skip

    mixed = [
        card("l1", "A", 0, 1, 0.5, 0.01, -0.001),
        card("l2", "B", 0, 3, 0.8, 0.02, -0.002),
        card("r1", "A", 0, 2, 10.0, 12, -2),
        card("r2", "A", 2, 2, 10.0, 12, -2),
        card("r3", "B", 1, 2, 5.0, 8, -3),
        card("r4", "A", 0, 2, 30.0, 31, -1),
        card("r5", "C", 1, 2, 4.0, 5, -1),
        card("r6", "B", 0, 2, 4.0, 5, 3),
        card("n1", "A", 0, 0, None, None, None),
        card("n2", "B", 2, 0, None, None, None),
        card("n3", "C", 1, 0, None, None, None),
    ]
    add("mixed_day", mixed, Limits(2, 100))
    add("reviews_limit_cuts_the_tail", mixed, Limits(10, 3))
    add("new_limit_used_up", mixed, Limits(2, 100, new_done_today=2))
    add(
        "subjects_alternate",
        [card(f"a{i}", "A", 0, 2, 5.0, 6 + i, -1) for i in range(4)] + [card("b1", "B", 0, 2, 5.0, 3, -1)],
        Limits(0, 100),
    )
    backlog = [card(f"o{i}", "A" if i % 2 else "B", i % 3, 2, 6.0, 20 + i, -(5 + i)) for i in range(30)]
    add("backlog_triggers_catchup_and_drops_new", [*backlog, *mixed[-3:]], Limits(5, 10))
    add("catchup_forced_off", [*backlog, *mixed[-3:]], Limits(5, 10), mode="off")
    add("catchup_forced_on_small_queue", mixed, Limits(5, 100), mode="on")
    add("old_but_small_backlog", [card("x1", "A", 0, 2, 5.0, 30, -10)], Limits(5, 100))
    end = now + timedelta(hours=14)
    add(
        "day_end_includes_later_today",
        [card("t1", "A", 0, 2, 5.0, 4, 0.3), card("t2", "A", 0, 2, 5.0, 4, 2)],
        Limits(0, 100),
        day_end=end,
    )
    return {"cases": cases}


def main() -> None:
    OUT.mkdir(exist_ok=True)
    for name, data in (
        ("fsrs6_cases.json", fsrs_cases()),
        ("folding_cases.json", folding_cases()),
        ("queue_cases.json", queue_cases()),
    ):
        (OUT / name).write_text(json.dumps(data, indent=1) + "\n", encoding="utf-8")
        print(name, len(data.get("cases", [])))


if __name__ == "__main__":
    main()
