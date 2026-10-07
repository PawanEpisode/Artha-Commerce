"""Choosing the day's motivation message: phases, the 60 day no-repeat rule, tone relaxation and the shortages."""

from datetime import date, timedelta

import pytest

from modules.notifications.domain.enums import MessagePhase as Phase
from modules.notifications.domain.motivation import (
    NO_REPEAT_DAYS,
    Candidate,
    Shortage,
    choose,
    is_recent,
    phase_for,
    recent_since,
)

TODAY = date(2026, 10, 7)


def c(name, tone="calm", phase="any"):
    return Candidate(id=name, tone=tone, phase=phase)


def pick(candidates, *, recent=(), tone="calm", phase=None, seed="u:2026-10-07"):
    return choose(candidates, recent_ids=recent, tone=tone, phase=phase, seed=seed)


# --- phases ---------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("days_left", "phase"),
    [
        (None, None),
        (-1, None),  # the exam date has passed
        (0, Phase.EXAM_DAY),
        (1, Phase.FINAL_WEEK),
        (7, Phase.FINAL_WEEK),
        (8, Phase.NEAR),
        (30, Phase.NEAR),
        (31, Phase.FAR),
        (400, Phase.FAR),
    ],
)
def test_the_phase_follows_the_days_left(days_left, phase):
    assert phase_for(days_left) is phase


# --- the 60 day rule --------------------------------------------------------------------------------------------------


def test_a_message_can_return_exactly_sixty_days_after_it_was_shown_and_not_before():
    assert NO_REPEAT_DAYS == 60
    assert is_recent(TODAY - timedelta(days=59), TODAY)
    assert not is_recent(TODAY - timedelta(days=60), TODAY)
    assert is_recent(TODAY, TODAY)
    assert is_recent(TODAY + timedelta(days=1), TODAY)  # a date from the future (clock skew) is never "long ago"


def test_recent_since_is_the_first_day_that_still_counts():
    assert recent_since(TODAY) == TODAY - timedelta(days=59)
    assert is_recent(recent_since(TODAY), TODAY) and not is_recent(recent_since(TODAY) - timedelta(days=1), TODAY)


def test_recently_shown_messages_are_never_chosen():
    pool = [c("a"), c("b"), c("d")]
    for seed in map(str, range(30)):
        assert pick(pool, recent={"a", "b"}, seed=seed).candidate.id == "d"


def test_one_message_left_is_that_message():
    assert pick([c("only")]).candidate.id == "only"


# --- shortages: nothing is repeated to fill a gap -----------------------------------------------------------------------


def test_an_empty_library_answers_empty():
    result = pick([])
    assert result.candidate is None and result.shortage is Shortage.EMPTY


def test_a_library_that_was_all_seen_answers_exhausted_and_not_a_repeat():
    result = pick([c("a"), c("b")], recent={"a", "b"})
    assert result.candidate is None and result.shortage is Shortage.EXHAUSTED


def test_messages_for_another_phase_do_not_count_as_candidates_but_the_library_is_not_empty():
    # Only an exam day line exists, and it is not exam day: nothing fits today, yet the library has lines.
    result = pick([c("x", phase="exam_day")], phase=Phase.FAR)
    assert result.candidate is None and result.shortage is Shortage.EXHAUSTED


# --- phase and tone ordering ---------------------------------------------------------------------------------------


def test_a_phase_line_in_the_students_tone_comes_first():
    pool = [c("any-calm"), c("final-calm", phase="final_week"), c("final-driven", tone="driven", phase="final_week")]
    for seed in map(str, range(20)):
        assert pick(pool, phase=Phase.FINAL_WEEK, seed=seed).candidate.id == "final-calm"


def test_without_an_exam_date_only_lines_for_any_day_are_used():
    pool = [c("any"), c("final", phase="final_week"), c("far", phase="far")]
    for seed in map(str, range(20)):
        assert pick(pool, phase=None, seed=seed).candidate.id == "any"


def test_a_line_for_a_different_phase_is_never_used():
    pool = [c("exam", phase="exam_day"), c("any")]
    for seed in map(str, range(20)):
        assert pick(pool, phase=Phase.NEAR, seed=seed).candidate.id == "any"


def test_the_tone_is_preferred_then_relaxed():
    pool = [c("calm-1"), c("driven-1", tone="driven")]
    for seed in map(str, range(20)):
        assert pick(pool, tone="driven", seed=seed).candidate.id == "driven-1"
    assert (
        pick(pool, tone="driven", recent={"driven-1"}).candidate.id == "calm-1"
    )  # tone exhausted: relax, don't repeat


def test_the_order_of_the_four_groups():
    pool = [
        c("t-p", "driven", "near"),  # 1. their tone, this phase
        c("t-a", "driven", "any"),  # 2. their tone, any day
        c("o-p", "calm", "near"),  # 3. other tone, this phase
        c("o-a", "calm", "any"),  # 4. other tone, any day
    ]
    seen: set[str] = set()
    order = []
    for _ in range(4):
        result = pick(pool, recent=seen, tone="driven", phase=Phase.NEAR)
        order.append(result.candidate.id)
        seen.add(result.candidate.id)
    assert order == ["t-p", "t-a", "o-p", "o-a"]
    assert pick(pool, recent=seen, tone="driven", phase=Phase.NEAR).shortage is Shortage.EXHAUSTED


# --- determinism ----------------------------------------------------------------------------------------------------


def test_the_same_seed_always_picks_the_same_line_whatever_the_input_order():
    pool = [c(str(n)) for n in range(12)]
    first = pick(pool, seed="student:2026-10-07").candidate.id
    assert pick(list(reversed(pool)), seed="student:2026-10-07").candidate.id == first
    assert all(pick(pool, seed="student:2026-10-07").candidate.id == first for _ in range(5))


def test_different_days_spread_over_the_group():
    pool = [c(str(n)) for n in range(12)]
    picked = {pick(pool, seed=f"student:{day}").candidate.id for day in range(60)}
    assert len(picked) >= 8


def test_sixty_days_in_a_row_never_repeat_when_the_library_is_big_enough():
    pool = [c(f"m{n:02d}") for n in range(NO_REPEAT_DAYS)]
    seen: set[str] = set()
    for day in range(NO_REPEAT_DAYS):
        result = pick(pool, recent=seen, seed=f"student:{day}")
        assert result.candidate is not None and result.candidate.id not in seen
        seen.add(result.candidate.id)
    assert pick(pool, recent=seen, seed="student:60").shortage is Shortage.EXHAUSTED
