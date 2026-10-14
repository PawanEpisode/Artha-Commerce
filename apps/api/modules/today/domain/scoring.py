"""
The score of one candidate (PRD 5.4 step 2). Integers only.

    raw      = 35*urgency + 25*importance + 25*weakness + 15*freshness            # 0..10000, "base" is raw / 10
    score    = raw * phase_multiplier% * provider_weight% / 100000                # exact for the PRD 5.6 worked example
    score   += 300 if must_do
    score   -= 40 * min(3, miss_count)                                            # anti-nag

Providers only give the four signals (0..100); they never see or set the final score, so no provider can dominate another.
"""

from __future__ import annotations

from dataclasses import dataclass

from .constants import MISS_PENALTY, MISS_PENALTY_MAX_MISSES, MUST_DO_BONUS

W_URGENCY, W_IMPORTANCE, W_WEAKNESS, W_FRESHNESS = 35, 25, 25, 15


@dataclass(frozen=True)
class Scored:
    score: int
    base: int  # raw / 10, what "Why this?" shows
    phase_mult: int
    provider_weight: int
    must_do: bool
    miss_penalty: int


def valid_signal(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and 0 <= value <= 100


def raw_base(urgency: int, importance: int, weakness: int, freshness: int) -> int:
    return W_URGENCY * urgency + W_IMPORTANCE * importance + W_WEAKNESS * weakness + W_FRESHNESS * freshness


def score_candidate(
    *,
    urgency: int,
    importance: int,
    weakness: int,
    freshness: int,
    phase_mult: int,
    provider_weight: int = 100,
    must_do: bool = False,
    miss_count: int = 0,
) -> Scored:
    raw = raw_base(urgency, importance, weakness, freshness)
    score = raw * phase_mult * provider_weight // 100_000
    if must_do:
        score += MUST_DO_BONUS
    penalty = MISS_PENALTY * min(MISS_PENALTY_MAX_MISSES, max(0, miss_count))
    score -= penalty
    return Scored(
        score=score,
        base=raw // 10,
        phase_mult=phase_mult,
        provider_weight=provider_weight,
        must_do=must_do,
        miss_penalty=penalty,
    )
