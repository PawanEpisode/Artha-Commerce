"""Property tests: replay is order, duplicate and void invariant; intervals and retrievability behave monotonically."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from hypothesis import given, settings
from hypothesis import strategies as st

from modules.recall.domain import fsrs6
from modules.recall.domain.folding import ReviewEvent, ScheduleEvent, apply_event, fold, new_card_state

W = fsrs6.DEFAULT_WEIGHTS
T0 = datetime(2026, 3, 2, 8, tzinfo=UTC)
CFG = fsrs6.Cfg(fuzz=True)

gaps = st.sampled_from([1, 5, 30, 600, 1440, 3000, 20000, 90000])
ratings = st.sampled_from([1, 2, 3, 3, 4])


@st.composite
def histories(draw):
    n = draw(st.integers(1, 12))
    t, events = T0, []
    for i in range(n):
        t += timedelta(minutes=draw(gaps) + i)  # strictly increasing, so ties never decide the order
        if draw(st.integers(0, 9)) == 0:
            events.append(
                ScheduleEvent(
                    f"s{i}",
                    t,
                    draw(st.sampled_from(["forget", "content_reset", "postpone", "unpostpone"])),
                    t + timedelta(days=9),
                    3.0,
                )
            )
        else:
            events.append(ReviewEvent(f"r{i}", t, draw(ratings)))
    return events


@settings(max_examples=150, deadline=None)
@given(histories(), st.randoms(use_true_random=False))
def test_fold_ignores_input_order_and_duplicates(events, rnd):
    want = fold(events, W, CFG, card_id="c")
    shuffled = [*events, *rnd.sample(events, k=min(3, len(events)))]
    rnd.shuffle(shuffled)
    assert fold(shuffled, W, CFG, card_id="c") == want


@settings(max_examples=150, deadline=None)
@given(histories())
def test_fold_equals_the_incremental_path(events):
    state = new_card_state()
    for e in sorted(events, key=lambda e: (e.at, 0 if isinstance(e, ScheduleEvent) else 1, e.id)):
        state = apply_event(state, e, W, CFG, card_id="c")
    assert fold(events, W, CFG, card_id="c") == state


@settings(max_examples=100, deadline=None)
@given(histories())
def test_voided_reviews_leave_no_trace(events):
    voided = [ReviewEvent(f"v{i}", e.at + timedelta(seconds=1), 1, voided=True) for i, e in enumerate(events)]
    assert fold([*events, *voided], W, CFG, card_id="c") == fold(events, W, CFG, card_id="c")


@settings(max_examples=100, deadline=None)
@given(st.integers(1, 3), st.integers(1, 2000))
def test_a_better_rating_never_gives_a_shorter_interval(first, days):
    cfg = fsrs6.Cfg(fuzz=False)
    s0 = fsrs6.review(fsrs6.MemoryState(), first, T0, W, cfg, card_id="c").state
    s1 = fsrs6.review(s0, 3, T0 + timedelta(minutes=1), W, cfg, card_id="c").state
    s2 = fsrs6.review(s1, 3, T0 + timedelta(minutes=11), W, cfg, card_id="c").state
    now = T0 + timedelta(days=days)
    got = [fsrs6.review(s2, r, now, W, cfg, card_id="c").scheduled_days for r in (1, 2, 3, 4)]
    assert got[1] <= got[2] <= got[3]
    assert got[0] <= got[2]


@settings(max_examples=200, deadline=None)
@given(st.floats(0.01, 3000), st.floats(0, 4000), st.floats(0, 4000))
def test_retrievability_falls_with_time_and_stays_a_probability(stability, t1, t2):
    lo, hi = sorted((t1, t2))
    r_lo, r_hi = fsrs6.retrievability(stability, lo, W[20]), fsrs6.retrievability(stability, hi, W[20])
    assert 0.0 < r_hi <= r_lo <= 1.0


@settings(max_examples=100, deadline=None)
@given(st.floats(0.05, 3000), st.sampled_from([0.8, 0.85, 0.9, 0.95]))
def test_interval_is_clamped_and_matches_the_target_retention(stability, retention):
    n = fsrs6.interval_days(stability, retention, W[20], 365)
    assert 1 <= n <= 365
    if 3 <= n < 365:
        assert abs(fsrs6.retrievability(stability, n, W[20]) - retention) < 0.05


@given(st.text(max_size=40), st.integers(0, 10**6))
def test_fuzz_unit_is_in_range_and_stable(card_id, reps):
    u = fsrs6.fuzz_unit(card_id, reps)
    assert 0.0 <= u < 1.0
    assert u == fsrs6.fuzz_unit(card_id, reps)


def test_fold_trace_ends_in_the_same_state_as_fold_and_reports_each_review():
    import random
    from datetime import UTC, datetime, timedelta

    from modules.recall.domain.folding import fold_trace
    from modules.recall.domain.fsrs6 import DEFAULT_WEIGHTS, Cfg

    rng = random.Random(7)
    base = datetime(2026, 10, 1, 8, tzinfo=UTC)
    cfg = Cfg()
    for _ in range(25):
        events = [
            ReviewEvent(
                f"r{i}",
                base + timedelta(hours=rng.randint(0, 900)),
                rng.randint(1, 4),
                rng.random() > 0.2,
                rng.random() > 0.85,
            )
            for i in range(rng.randint(1, 15))
        ]
        if rng.random() > 0.5:
            events.append(ScheduleEvent("s1", base + timedelta(hours=rng.randint(0, 900)), "forget"))
        state, traces = fold_trace(events, DEFAULT_WEIGHTS, cfg, card_id="c1")
        assert state == fold(events, DEFAULT_WEIGHTS, cfg, card_id="c1")
        reviews = [e for e in events if isinstance(e, ReviewEvent)]
        assert set(traces) == {e.id for e in reviews}
        assert all(
            (t.outcome is not None) == (e.counts_for_scheduling and not e.voided)
            for e in reviews
            for t in [traces[e.id]]
        )
