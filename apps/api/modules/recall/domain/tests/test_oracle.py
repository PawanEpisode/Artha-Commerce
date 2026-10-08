"""py-fsrs as an oracle (D8): development only. Skipped when `fsrs` is not installed; with fuzz off we must match it."""

from __future__ import annotations

import random
from datetime import UTC, datetime, timedelta

import pytest

from modules.recall.domain import fsrs6

fsrs = pytest.importorskip("fsrs")


def test_matches_py_fsrs_on_10000_random_histories():
    rnd = random.Random(7)
    for h in range(10_000):
        steps = rnd.choice([(1, 10), (1,), (), (5, 15, 60)])
        rsteps = rnd.choice([(10,), (), (10, 30)])
        retention = rnd.choice([0.85, 0.9, 0.93])
        cap = rnd.choice([365, 60, 36500])
        sched = fsrs.Scheduler(
            desired_retention=retention,
            learning_steps=tuple(timedelta(minutes=m) for m in steps),
            relearning_steps=tuple(timedelta(minutes=m) for m in rsteps),
            maximum_interval=cap,
            enable_fuzzing=False,
        )
        cfg = fsrs6.Cfg(retention, steps, rsteps, cap, False)
        card, state, t = fsrs.Card(), fsrs6.MemoryState(), datetime(2026, 1, 1, 8, tzinfo=UTC)
        for i in range(rnd.randint(1, 14)):
            t += timedelta(minutes=rnd.choice([1, 5, 30, 600, 1440, 3000, 20000, 200000]) + rnd.randint(0, 50))
            rating = rnd.choice([1, 2, 3, 3, 3, 4])
            card, _ = sched.review_card(card, fsrs.Rating(rating), t)
            out = fsrs6.review(state, rating, t, fsrs6.DEFAULT_WEIGHTS, cfg, card_id="x")
            state = out.state
            where = f"history {h}, review {i}"
            assert state.phase == int(card.state), where
            assert state.step == card.step, where
            assert abs(state.stability - card.stability) < 1e-6, where
            assert abs(state.difficulty - card.difficulty) < 1e-6, where
            assert abs((out.due_at - card.due).total_seconds()) < 1, where
