"""
Pure mathematical functions for Performance Analytics (F-10).
Covers Wilson score intervals, Beta shrinkage (empirical Bayes), exponential time decay, and pace ratios.
"""

from __future__ import annotations

import math
from decimal import Decimal

from .limits import (
    DEFAULT_HALF_LIFE_DAYS,
    DEFAULT_LOOKBACK_FACTOR,
    DEFAULT_MODE_WEIGHT_EXAM,
    DEFAULT_PRIOR_MEAN,
    DEFAULT_PRIOR_STRENGTH,
    DEFAULT_REPEAT_WEIGHT,
)


def wilson_score_interval(
    correct: float | Decimal,
    total: int,
    confidence_z: float = 1.96,
) -> tuple[float, float, float]:
    """
    Computes Wilson score confidence interval (center, lower, upper).
    Returns (center, lower, upper) in [0.0, 1.0].
    If total <= 0, returns (0.0, 0.0, 0.0).
    """
    if total <= 0:
        return (0.0, 0.0, 0.0)

    p_hat = float(correct) / float(total)
    z = float(confidence_z)
    z2 = z * z
    n = float(total)

    denominator = 1.0 + z2 / n
    center = (p_hat + z2 / (2.0 * n)) / denominator
    spread = (z / denominator) * math.sqrt((p_hat * (1.0 - p_hat) / n) + (z2 / (4.0 * n * n)))

    lower = max(0.0, center - spread)
    upper = min(1.0, center + spread)
    return (center, lower, upper)


def compute_time_decay_weight(
    days_ago: int,
    half_life_days: int = DEFAULT_HALF_LIFE_DAYS,
    lookback_factor: int = DEFAULT_LOOKBACK_FACTOR,
    is_repeat: bool = False,
    mode: str = "untimed",
    mode_weight_exam: Decimal = DEFAULT_MODE_WEIGHT_EXAM,
    repeat_weight: Decimal = DEFAULT_REPEAT_WEIGHT,
) -> float:
    """
    Calculates time-decay evidence weight w = 2^(-days_ago / H).
    Returns 0.0 if days_ago exceeds lookback window (lookback_factor * half_life_days).
    Applies repeat_weight and mode_weight_exam adjustments.
    """
    if days_ago < 0:
        days_ago = 0

    max_lookback = half_life_days * lookback_factor
    if days_ago > max_lookback:
        return 0.0

    # Base exponential decay
    w = math.pow(2.0, -float(days_ago) / float(half_life_days))

    # Mode adjustment
    if mode == "exam":
        w *= float(mode_weight_exam)

    # Repeat penalty
    if is_repeat:
        w *= float(repeat_weight)

    return w


def beta_shrinkage(
    credit_sum: float | Decimal,
    weight_sum: float | Decimal,
    prior_mean: float | Decimal = DEFAULT_PRIOR_MEAN,
    prior_strength: float | Decimal = DEFAULT_PRIOR_STRENGTH,
) -> float:
    """
    Empirical Bayes Beta shrinkage:
    mu = (k * p0 + sum(w_i * y_i)) / (k + sum(w_i))
    Pulls sparse observations toward the prior mean p0.
    """
    k = float(prior_strength)
    p0 = float(prior_mean)
    c = float(credit_sum)
    w = float(weight_sum)

    denom = k + w
    if denom <= 0:
        return p0

    return (k * p0 + c) / denom


def compute_pace_ratio(actual_ms: int, target_ms: int) -> float | None:
    """
    Calculates actual time vs target time ratio.
    Returns None if target_ms <= 0 or actual_ms <= 0.
    """
    if target_ms <= 0 or actual_ms <= 0:
        return None
    return float(actual_ms) / float(target_ms)
