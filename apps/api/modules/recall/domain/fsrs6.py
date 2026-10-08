"""
FSRS-6 as a pure, versioned function (PRD 4.3, ERD 3.2). `SCHEDULER_VERSION = "fsrs-6.0"`.

This is our own implementation of the open-source algorithm (py-fsrs 6.3.2 and ts-fsrs implement the same maths): the
server and the browser must produce identical intervals, so neither runtime depends on a library, fuzz is deterministic
(a hash of the card id and its review count, not a random number) and rounding is fixed. The libraries are used only as an
oracle in the tests (dev dependency, skipped when absent).

Conventions (ERD D7, pinned by `tests/vectors/fsrs6_cases.json`):

- Every instant is a timezone-aware UTC `datetime`. `elapsed_days` is the whole number of days between the previous counted
  review and now (floor, never negative). A review less than one day after the previous one uses the same-day formulas.
- Stability and difficulty are doubles here; the database rounds them to `real` only on write.
- Intervals are whole days: rounded half up, at least 1, at most `max_interval_days`. Learning and relearning steps are
  minutes and give fractional days.
- A card in `PHASE_NEW` is treated exactly like a Learning card at step 0 with no stability (py-fsrs' first review).
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import datetime, timedelta

from .limits import (
    AGAIN,
    EASY,
    GOOD,
    HARD,
    MINUTES_PER_DAY,
    PHASE_LEARNING,
    PHASE_NEW,
    PHASE_RELEARNING,
    PHASE_REVIEW,
    SCHEDULER_VERSION,
    SECONDS_PER_DAY,
)

__all__ = [
    "DEFAULT_WEIGHTS",
    "SCHEDULER_VERSION",
    "Cfg",
    "MemoryState",
    "Preview",
    "ReviewOutcome",
    "cap_stability",
    "elapsed_whole_days",
    "format_interval",
    "fuzz_unit",
    "interval_days",
    "preview",
    "retrievability",
    "review",
    "validate_weights",
]

DEFAULT_WEIGHTS: tuple[float, ...] = (
    0.212,
    1.2931,
    2.3065,
    8.2956,
    6.4133,
    0.8334,
    3.0194,
    0.001,
    1.8722,
    0.1666,
    0.796,
    1.4835,
    0.0614,
    0.2629,
    1.6483,
    0.6014,
    1.8729,
    0.5425,
    0.0912,
    0.0658,
    0.1542,
)

STABILITY_MIN = 0.001
_LOWER = (STABILITY_MIN,) * 4 + (
    1.0,
    0.001,
    0.001,
    0.001,
    0.0,
    0.0,
    0.001,
    0.001,
    0.001,
    0.001,
    0.0,
    0.0,
    1.0,
    0.0,
    0.0,
    0.0,
    0.1,
)
_UPPER = (100.0,) * 4 + (10.0, 4.0, 4.0, 0.75, 4.5, 0.8, 3.5, 5.0, 0.25, 0.9, 4.0, 1.0, 6.0, 2.0, 2.0, 0.8, 0.8)
MIN_DIFFICULTY = 1.0
MAX_DIFFICULTY = 10.0

# Deterministic fuzz: (start, end, factor) as in py-fsrs
_FUZZ_RANGES = ((2.5, 7.0, 0.15), (7.0, 20.0, 0.10), (20.0, math.inf, 0.05))


@dataclass(frozen=True)
class MemoryState:
    """What the scheduler remembers about one card. `due` is not part of it: it is an output (`ReviewOutcome.due_at`)."""

    phase: int = PHASE_NEW
    step: int | None = None
    stability: float | None = None
    difficulty: float | None = None
    last_review_at: datetime | None = None
    reps: int = 0
    lapses: int = 0
    last_lapse_at: datetime | None = None


@dataclass(frozen=True)
class Cfg:
    """The student's scheduling settings that change intervals (the study-day settings live in `scheduling`)."""

    desired_retention: float = 0.90
    learning_steps: tuple[int, ...] = (1, 10)  # minutes
    relearning_steps: tuple[int, ...] = (10,)  # minutes
    max_interval_days: int = 365
    fuzz: bool = True


@dataclass(frozen=True)
class ReviewOutcome:
    state: MemoryState
    scheduled_days: float  # the interval chosen, in days (a fraction for learning steps)
    due_at: datetime
    phase_before: int
    elapsed_days: int | None  # whole days since the previous counted review; None for the first review
    retrievability_before: float | None
    lapsed: bool


@dataclass(frozen=True)
class Preview:
    rating: int
    scheduled_days: float
    due_at: datetime
    label: str


def validate_weights(w: Sequence[float]) -> tuple[float, ...]:
    """The 21 weights, checked against the bounds; raises `ValueError` listing every weight that is out of range."""
    if len(w) != len(_LOWER):
        raise ValueError(f"Expected {len(_LOWER)} weights, got {len(w)}.")
    bad = [
        f"w[{i}]={x} is outside [{lo}, {hi}]"
        for i, (x, lo, hi) in enumerate(zip(w, _LOWER, _UPPER, strict=True))
        if not lo <= x <= hi
    ]
    if bad:
        raise ValueError("Weights out of bounds: " + "; ".join(bad))
    return tuple(float(x) for x in w)


def _round_half_up(x: float) -> int:
    return math.floor(x + 0.5)


def _factor(w20: float) -> float:
    return 0.9 ** (-1.0 / w20) - 1.0


def elapsed_whole_days(last: datetime | None, now: datetime) -> int | None:
    if last is None:
        return None
    return max(0, math.floor((now - last).total_seconds() / SECONDS_PER_DAY))


def retrievability(stability: float, elapsed_days: float, w20: float) -> float:
    """Predicted probability of recall: `(1 + F * t / S) ^ -w20`. Never stored; computed from stability and elapsed time."""
    return (1.0 + _factor(w20) * max(0.0, elapsed_days) / stability) ** (-w20)


def interval_days(stability: float, retention: float, w20: float, max_interval: int) -> int:
    """Whole days until recall probability falls to `retention`, clamped to `[1, max_interval]`."""
    raw = (stability / _factor(w20)) * (retention ** (-1.0 / w20) - 1.0)
    return min(max(_round_half_up(raw), 1), max_interval)


def fuzz_unit(card_id: object, reps: int) -> float:
    """Deterministic number in [0, 1): FNV-1a (32 bit) over the UTF-8 bytes of `"{card_id}:{reps}"` divided by 2^32."""
    h = 0x811C9DC5
    for byte in f"{card_id}:{reps}".encode():
        h = ((h ^ byte) * 0x01000193) & 0xFFFFFFFF
    return h / 4294967296.0


def _fuzzed(days: int, max_interval: int, card_id: object, reps: int) -> int:
    if days < 2.5:
        return days
    delta = 1.0
    for start, end, factor in _FUZZ_RANGES:
        delta += factor * max(min(float(days), end) - start, 0.0)
    lo = max(2, _round_half_up(days - delta))
    hi = min(_round_half_up(days + delta), max_interval)
    lo = min(lo, hi)
    pick = _round_half_up(fuzz_unit(card_id, reps) * (hi - lo + 1) + lo)
    return min(pick, max_interval)


def _clamp_d(d: float) -> float:
    return min(max(d, MIN_DIFFICULTY), MAX_DIFFICULTY)


def _clamp_s(s: float) -> float:
    return max(s, STABILITY_MIN)


def _init_stability(w: Sequence[float], rating: int) -> float:
    return _clamp_s(w[rating - 1])


def _init_difficulty(w: Sequence[float], rating: int, *, clamp: bool) -> float:
    d = w[4] - math.exp(w[5] * (rating - 1)) + 1.0
    return _clamp_d(d) if clamp else d


def _next_difficulty(w: Sequence[float], d: float, rating: int) -> float:
    delta = -(w[6] * (rating - 3))
    target = d + (10.0 - d) * delta / 9.0
    reverted = w[7] * _init_difficulty(w, EASY, clamp=False) + (1.0 - w[7]) * target
    return _clamp_d(reverted)


def _short_term_stability(w: Sequence[float], s: float, rating: int) -> float:
    inc = math.exp(w[17] * (rating - 3 + w[18])) * (s ** -w[19])
    if rating >= HARD:
        inc = max(inc, 1.0)
    return _clamp_s(s * inc)


def _recall_stability(w: Sequence[float], d: float, s: float, r: float, rating: int) -> float:
    hard = w[15] if rating == HARD else 1.0
    easy = w[16] if rating == EASY else 1.0
    return s * (1.0 + math.exp(w[8]) * (11.0 - d) * (s ** -w[9]) * (math.exp((1.0 - r) * w[10]) - 1.0) * hard * easy)


def _forget_stability(w: Sequence[float], d: float, s: float, r: float) -> float:
    long_term = w[11] * (d ** -w[12]) * (((s + 1.0) ** w[13]) - 1.0) * math.exp((1.0 - r) * w[14])
    short_term = s / math.exp(w[17] * w[18])
    return min(long_term, short_term)


def _next_stability(w: Sequence[float], d: float, s: float, r: float, rating: int) -> float:
    nxt = _forget_stability(w, d, s, r) if rating == AGAIN else _recall_stability(w, d, s, r, rating)
    return _clamp_s(nxt)


def _hard_minutes(steps: Sequence[int], step: int) -> float:
    """Hard keeps the step: 1.5x a lone first step, the mean of the first two for step 0, else the step itself."""
    if step == 0 and len(steps) == 1:
        return steps[0] * 1.5
    if step == 0 and len(steps) >= 2:
        return (steps[0] + steps[1]) / 2.0
    return float(steps[step])


def review(
    state: MemoryState, rating: int, now: datetime, w: Sequence[float], cfg: Cfg, *, card_id: object
) -> ReviewOutcome:
    """
    Apply one rating (1 Again, 2 Hard, 3 Good, 4 Easy) at `now` and return the new memory state, the interval and the due time.
    Pure and deterministic: the same arguments always give the same result, in Python and in the TypeScript twin.
    """
    if rating not in (1, 2, 3, 4):
        raise ValueError(f"Unknown rating: {rating}")
    w20 = w[20]
    phase_before = state.phase
    phase = PHASE_LEARNING if state.phase == PHASE_NEW else state.phase
    step = state.step or 0
    elapsed = elapsed_whole_days(state.last_review_at, now)
    s, d = state.stability, state.difficulty
    r_before = retrievability(s, elapsed or 0, w20) if s is not None and elapsed is not None else None

    # Memory update. The first review sets the initial values; later ones use the same-day or the long-term formulas.
    # Stability uses the difficulty from before this review; difficulty is updated afterwards, on every path.
    if s is None or d is None:
        s, d = _init_stability(w, rating), _init_difficulty(w, rating, clamp=True)
    else:
        if elapsed is not None and elapsed < 1:
            s2 = _short_term_stability(w, s, rating)
        else:
            s2 = _next_stability(w, d, s, r_before if r_before is not None else 1.0, rating)
        s, d = s2, _next_difficulty(w, d, rating)

    lapsed = phase == PHASE_REVIEW and rating == AGAIN
    new_phase, new_step = phase, (step if phase != PHASE_REVIEW else None)
    minutes: float | None = None  # interval in minutes while the card stays in its steps; None means it graduates

    if phase == PHASE_REVIEW:
        if lapsed and cfg.relearning_steps:
            new_phase, new_step, minutes = PHASE_RELEARNING, 0, float(cfg.relearning_steps[0])
    else:
        steps = cfg.learning_steps if phase == PHASE_LEARNING else cfg.relearning_steps
        if not steps or (step >= len(steps) and rating >= HARD):
            pass  # graduates (also: the student shortened their steps while this card was in them)
        elif rating == AGAIN:
            new_step, minutes = 0, float(steps[0])
        elif rating == HARD:
            minutes = _hard_minutes(steps, step)
        elif rating == GOOD and step + 1 < len(steps):
            new_step, minutes = step + 1, float(steps[step + 1])
        # Good on the last step and Easy graduate

    if minutes is None:
        new_phase, new_step = PHASE_REVIEW, None
        days = interval_days(s, cfg.desired_retention, w20, cfg.max_interval_days)
        if cfg.fuzz:
            days = _fuzzed(days, cfg.max_interval_days, card_id, state.reps)
        scheduled = float(days)
    else:
        scheduled = minutes / MINUTES_PER_DAY

    new_state = MemoryState(
        phase=new_phase,
        step=new_step,
        stability=s,
        difficulty=d,
        last_review_at=now,
        reps=state.reps + 1,
        lapses=state.lapses + (1 if lapsed else 0),
        last_lapse_at=now if lapsed else state.last_lapse_at,
    )
    return ReviewOutcome(
        state=new_state,
        scheduled_days=scheduled,
        due_at=now + timedelta(days=scheduled),
        phase_before=phase_before,
        elapsed_days=elapsed,
        retrievability_before=r_before,
        lapsed=lapsed,
    )


def format_interval(days: float) -> str:
    """The text under a rating button: `10 min`, `2 h`, `5 d`, `3 mo`, `1.5 y`. Mirrored in `lib/fsrs6.ts` and vector-tested."""
    minutes = _round_half_up(days * MINUTES_PER_DAY)
    if minutes < 60:
        return f"{max(minutes, 1)} min"
    if minutes < MINUTES_PER_DAY:
        return f"{_round_half_up(minutes / 60)} h"
    whole = _round_half_up(days)
    if whole < 31:
        return f"{whole} d"
    if whole < 365:
        return f"{_round_half_up(whole / 30.4375)} mo"
    years = _round_half_up(whole / 365.0 * 10) / 10
    return f"{years:g} y"


def preview(state: MemoryState, now: datetime, w: Sequence[float], cfg: Cfg, *, card_id: object) -> dict[int, Preview]:
    """The four buttons: what each rating would schedule. Equal to what `review` applies, because fuzz is deterministic."""
    out: dict[int, Preview] = {}
    for rating in (1, 2, 3, 4):
        o = review(state, rating, now, w, cfg, card_id=card_id)
        out[rating] = Preview(rating, o.scheduled_days, o.due_at, format_interval(o.scheduled_days))
    return out


def cap_stability(state: MemoryState, cap_days: float) -> MemoryState:
    """`content_reset`: a substantive content change softens the memory (stability capped, default 3 days)."""
    if state.stability is None or state.stability <= cap_days:
        return state
    return replace(state, stability=cap_days)
