"""
Regenerates `vectors/exam_cases.json`: the exam horizon, retention boost, R_exam, quick set, cram window, pacing and a fold with
the boost, from our own domain (no oracle exists for these; the PRD defines them). The TypeScript twin must reproduce them.

    cd apps/api && python -m modules.recall.domain.tests.make_exam_vectors

Then copy the file to apps/web/src/modules/recall/lib/vectors/ (a web test fails when the copies differ). A change in the JSON is
a change of behaviour: review it in the pull request.
"""

from __future__ import annotations

import json
import random
from datetime import UTC, datetime, timedelta
from pathlib import Path

from modules.recall.domain import exam, fsrs6
from modules.recall.domain.folding import ReviewEvent, effective_due, fold

OUT = Path(__file__).parent / "vectors" / "exam_cases.json"
EXAM = datetime(2026, 12, 20, 4, 0, tzinfo=UTC)
W = list(fsrs6.DEFAULT_WEIGHTS)
W20 = W[20]


def iso(t: datetime | None) -> str | None:
    return None if t is None else t.isoformat().replace("+00:00", "Z")


def card_id(rnd: random.Random) -> str:
    return f"{rnd.getrandbits(32):08x}-{rnd.getrandbits(16):04x}-4{rnd.getrandbits(12):03x}-8000-{rnd.getrandbits(48):012x}"


def horizon_cases(rnd: random.Random) -> list[dict]:
    out = []
    for i in range(80):
        now = EXAM - timedelta(days=rnd.choice([0.3, 0.9, 1.5, 3, 8, 20, 45, 89, 91, 120]) + rnd.random() * 0.4)
        due = now + timedelta(days=rnd.uniform(-3, 220))
        last = None if rnd.random() < 0.1 else now - timedelta(days=rnd.uniform(0, 100))
        cid = card_id(rnd)
        enabled = rnd.random() > 0.1
        got = exam.horizon(due, last, EXAM, cid, now, enabled=enabled)
        out.append(
            {
                "name": f"horizon:{i}",
                "due": iso(due),
                "last_review": iso(last),
                "exam": iso(EXAM),
                "card_id": cid,
                "now": iso(now),
                "enabled": enabled,
                "expected": iso(got),
            }
        )
    return out


def retention_cases() -> list[dict]:
    out = []
    for importance in (0, 1, 2):
        for desired in (0.85, 0.9, 0.93, 0.97):
            for left in (None, -1.0, 0.0, 0.5, 29.9, 30.0, 30.1, 90.0):
                for enabled in (True, False):
                    got = exam.retention_for(importance, desired, left, enabled=enabled)
                    out.append(
                        {
                            "importance": importance,
                            "desired": desired,
                            "left": left,
                            "enabled": enabled,
                            "expected": got,
                        }
                    )
    return out


def r_exam_cases(rnd: random.Random) -> list[dict]:
    out = []
    for _ in range(25):
        last = EXAM - timedelta(days=rnd.uniform(0.5, 120))
        stab = None if rnd.random() < 0.1 else rnd.uniform(0.5, 300)
        out.append(
            {
                "stability": stab,
                "last_review": iso(last),
                "exam": iso(EXAM),
                "w20": W20,
                "expected": exam.r_exam(stab, last, EXAM, W20),
            }
        )
    return out


def quick_cases(rnd: random.Random) -> list[dict]:
    out = []
    for i in range(12):
        now = EXAM - timedelta(days=rnd.choice([1.5, 2.5, 5, 12, 30, 44]) + rnd.random())
        cards = []
        for j in range(rnd.randint(0, 60)):
            phase = rnd.choice([0, 1, 2, 2, 3])
            cards.append(
                {
                    "id": f"c{j:03d}",
                    "importance": rnd.randint(0, 2),
                    "phase": phase,
                    "stability": None if phase == 0 else rnd.uniform(0.5, 90),
                    "last_review": None if phase == 0 else iso(now - timedelta(days=rnd.uniform(0, 80))),
                }
            )
        minutes, median = rnd.choice([5, 15, 30, 120]), rnd.choice([8.0, 12.0, 25.0])
        plan = exam.quick_set(
            [exam.QuickCard(c["id"], c["importance"], c["phase"], c["stability"], datetime.fromisoformat(c["last_review"].replace("Z", "+00:00")) if c["last_review"] else None) for c in cards],
            EXAM, minutes, median, now, W20,
        )  # fmt: skip
        out.append(
            {
                "name": f"quick:{i}",
                "now": iso(now),
                "exam": iso(EXAM),
                "minutes": minutes,
                "median": median,
                "w20": W20,
                "cards": cards,
                "expected": {
                    "ids": list(plan.ids),
                    "candidates": plan.candidates,
                    "selected": plan.selected,
                    "cut_off": plan.cut_off,
                    "days_to_exam": plan.days_to_exam,
                    "window_days": plan.window_days,
                    "per_day": plan.per_day,
                    "minutes_per_day": plan.minutes_per_day,
                    "too_few": plan.too_few,
                },
            }
        )
    return out


def cram_cases() -> list[dict]:
    out = []
    for hours in (-5, 0, 0.1, 12, 23.9, 24, 24.1, 72):
        now = EXAM - timedelta(hours=hours)
        out.append({"now": iso(now), "exam": iso(EXAM), "expected": exam.cram_open(now, EXAM)})
    out.append({"now": iso(EXAM), "exam": None, "expected": False})
    return out


def pacing_cases() -> list[dict]:
    out = []
    for unseen in (0, 40, 300, 600):
        for left in (3.0, 14.0, 15.2, 60.4, 200.0):
            for limit in (0, 5, 10, 25):
                p = exam.pacing(unseen, left, limit)
                out.append(
                    {
                        "unseen": unseen,
                        "days_left": left,
                        "new_per_day": limit,
                        "expected": {
                            "unseen": p.unseen,
                            "window_days": p.window_days,
                            "new_per_day": p.new_per_day,
                            "introduced_at_limit": p.introduced_at_limit,
                            "needed_per_day": p.needed_per_day,
                            "feasible": p.feasible,
                        },
                    }
                )
    return out


def fold_cases(rnd: random.Random) -> list[dict]:
    """A card reviewed through the last month before the exam: the boost changes its intervals only for mandatory cards."""
    out = []
    for i in range(10):
        importance = rnd.choice([1, 2])
        cid = card_id(rnd)
        at = EXAM - timedelta(days=rnd.uniform(60, 90))
        events = []
        for k in range(rnd.randint(2, 9)):
            events.append({"id": f"e{k}", "at": iso(at), "rating": rnd.choice([1, 3, 3, 3, 4])})
            at += timedelta(days=rnd.uniform(1, 12))
        cfg = fsrs6.Cfg(fuzz=True)
        state = fold(
            [ReviewEvent(e["id"], datetime.fromisoformat(e["at"].replace("Z", "+00:00")), e["rating"]) for e in events],
            W, cfg, card_id=cid, cfg_for=lambda t, imp=importance, c=cfg: exam.cfg_at(c, imp, t, EXAM),
        )  # fmt: skip
        m = state.memory
        out.append(
            {
                "name": f"fold_boost:{i}",
                "card_id": cid,
                "importance": importance,
                "exam": iso(EXAM),
                "events": events,
                "expected": {
                    "phase": m.phase,
                    "stability": m.stability,
                    "difficulty": m.difficulty,
                    "reps": m.reps,
                    "lapses": m.lapses,
                    "due_scheduled_at": iso(state.due_scheduled_at),
                    "effective_due": iso(effective_due(state)),
                },
            }
        )
    return out


def main() -> None:
    rnd = random.Random(20261011)
    data = {
        "horizon": horizon_cases(rnd),
        "retention": retention_cases(),
        "r_exam": r_exam_cases(rnd),
        "quick": quick_cases(rnd),
        "cram": cram_cases(),
        "pacing": pacing_cases(),
        "fold_boost": fold_cases(rnd),
    }
    OUT.write_text(json.dumps(data, indent=1, sort_keys=True) + "\n")
    print(f"wrote {OUT} ({sum(len(v) for v in data.values())} cases)")


if __name__ == "__main__":
    main()
