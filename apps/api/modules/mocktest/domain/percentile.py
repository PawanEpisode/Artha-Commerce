"""
Cohort stats and percentile computation for F-08 Mock Tests (ERD Section 3.5.7).
"""

from __future__ import annotations

import math
from typing import Any


MIN_COHORT_FLOOR = 30
BAND_UPTO = 100


def compute_cohort_histogram(scores_pct: list[float]) -> dict[str, Any]:
    """
    Computes 50 bins of 2% each over scores 0 to 100.
    """
    counts = [0] * 50
    for s in scores_pct:
        clamped = max(0.0, min(100.0, float(s)))
        bin_idx = min(49, int(clamped // 2))
        counts[bin_idx] += 1

    return {"v": 1, "bin_pct": 2, "counts": counts}


def compute_cohort_quantiles(scores_pct: list[float]) -> dict[str, Any]:
    """
    Computes percentiles [5, 10, 15, ..., 95].
    """
    if not scores_pct:
        return {"v": 1, "p": [], "values": []}

    sorted_scores = sorted(scores_pct)
    n = len(sorted_scores)
    p_steps = list(range(5, 100, 5))
    values = []

    for p in p_steps:
        k = (n - 1) * (p / 100.0)
        f = math.floor(k)
        c = math.ceil(k)
        if f == c:
            val = sorted_scores[int(k)]
        else:
            val = sorted_scores[f] * (c - k) + sorted_scores[c] * (k - f)
        values.append(round(val, 2))

    return {"v": 1, "p": p_steps, "values": values}


def calculate_percentile_from_scores(scores_pct: list[float], student_score: float) -> float:
    """
    Computes percentile for student_score:
    100 * (count_below + 0.5 * count_equal) / n
    """
    if not scores_pct:
        return 0.0

    count_below = sum(1 for s in scores_pct if s < student_score)
    count_equal = sum(1 for s in scores_pct if s == student_score)
    n = len(scores_pct)

    return round(100.0 * (count_below + 0.5 * count_equal) / n, 1)


def get_percentile_view(
    student_score: float,
    cohort_n: int,
    all_scores: list[float] | None = None,
    percentile_val: float | None = None,
) -> dict[str, Any]:
    """
    Returns student display for percentile:
    - n < 30: "hidden" / not_enough_students
    - 30 <= n < 100: quartile band
    - n >= 100: exact percentile
    """
    if cohort_n < MIN_COHORT_FLOOR:
        return {
            "status": "unavailable",
            "reason": "not_enough_students",
            "message": f"Percentile requires at least {MIN_COHORT_FLOOR} student attempts. Currently {cohort_n}.",
            "n": cohort_n,
        }

    pct = (
        percentile_val
        if percentile_val is not None
        else calculate_percentile_from_scores(all_scores or [], student_score)
    )

    if cohort_n < BAND_UPTO:
        # Quartile bands: Top 25%, Top 25-50%, Top 50-75%, Bottom 25%
        if pct >= 75:
            band = "Top 25%"
        elif pct >= 50:
            band = "Top 25% to 50%"
        elif pct >= 25:
            band = "Top 50% to 75%"
        else:
            band = "Bottom 25%"

        return {
            "status": "band",
            "band": band,
            "percentile": pct,
            "n": cohort_n,
        }

    return {
        "status": "percentile",
        "percentile": round(pct),
        "n": cohort_n,
    }
