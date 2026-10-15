"""
Adaptive practice IRT/Elo domain mathematics (F-05 ERD 3.5).
Pure functions for logistic item response, Bayesian item difficulty,
and Elo-style online ability (theta) updates.
"""

from __future__ import annotations

import math
from collections.abc import Sequence


def compute_item_difficulty(
    editorial_difficulty: int | None,
    attempts: int = 0,
    p_value: float | None = None,
) -> float:
    """Computes blended item difficulty b in logit units."""
    # Prior b0 from editorial difficulty
    if editorial_difficulty is not None and 1 <= editorial_difficulty <= 5:
        b0 = (float(editorial_difficulty) - 3.0) * 0.75
    else:
        b0 = 0.0

    n = attempts if attempts >= 30 else 0
    if n == 0 or p_value is None:
        return b0

    p_clamped = max(0.05, min(0.95, float(p_value)))
    b_emp = -math.log(p_clamped / (1.0 - p_clamped))
    return (n * b_emp + 20.0 * b0) / (n + 20.0)


def predict_success_probability(theta: float, b: float) -> float:
    """1-PL logistic model probability P(correct | theta, b)."""
    diff = theta - b
    # Avoid overflow
    if diff > 15:
        return 1.0
    if diff < -15:
        return 0.0
    return 1.0 / (1.0 + math.exp(-diff))


def compute_k_factor(n_prior: int, is_subject_scope: bool = False) -> float:
    """K(n_s) = max(0.10, 0.90 / (1 + 0.05 * n_s)), scaled by 0.5 for subject scope."""
    base_k = max(0.10, 0.90 / (1.0 + 0.05 * float(n_prior)))
    return base_k * 0.5 if is_subject_scope else base_k


def update_theta_from_answers(
    initial_theta: float,
    answers: Sequence[tuple[str, float]],  # list of (result, item_difficulty_b)
    n_prior: int,
    is_subject_scope: bool = False,
) -> tuple[float, int, int]:
    """
    Updates ability theta sequentially.
    Returns: (new_theta, new_n, correct_count)
    Skipped answers do not alter theta.
    """
    theta = float(initial_theta)
    curr_n = n_prior
    correct_count = 0

    for result, b in answers:
        if result == "skipped":
            continue

        if result == "correct":
            outcome = 1.0
            correct_count += 1
        elif result == "incorrect":
            outcome = 0.0
        elif result == "partial":
            outcome = 0.5
        else:
            continue

        p = predict_success_probability(theta, b)
        k = compute_k_factor(curr_n, is_subject_scope=is_subject_scope)
        theta += k * (outcome - p)
        curr_n += 1

    return round(theta, 3), curr_n, correct_count
