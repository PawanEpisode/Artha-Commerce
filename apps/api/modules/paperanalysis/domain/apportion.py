"""
Pure apportionment function for F-11.
Distributes a question's marks across chapters using largest remainder in 0.5-mark steps (or 0.1).
Guarantees exact Decimal sum and determinism.
Reference: ERD 3.5.
"""

from __future__ import annotations

from collections.abc import Sequence
from decimal import ROUND_FLOOR, Decimal


def apportion(
    marks: Decimal,
    weights: Sequence[Decimal | float],
    step: Decimal | None = None,
) -> list[Decimal]:
    """
    Apportions `marks` across components according to `weights`.
    Step is 0.5 Decimal by default, or 0.1 if marks is not a multiple of 0.5.
    Result sums to `marks` exactly.
    """
    if marks <= Decimal("0"):
        raise ValueError("Marks must be strictly positive.")
    if not weights:
        raise ValueError("Weights cannot be empty.")

    dec_weights = [Decimal(str(w)) for w in weights]
    if any(w < Decimal("0") for w in dec_weights):
        raise ValueError("Weights must be non-negative.")

    total_weight = sum(dec_weights)
    if total_weight <= Decimal("0"):
        raise ValueError("Sum of weights must be positive.")

    # Determine step: 0.5 if marks is a multiple of 0.5, else 0.1
    if step is None:
        if (marks % Decimal("0.5")) == Decimal("0"):
            step = Decimal("0.5")
        else:
            step = Decimal("0.1")

    n = len(dec_weights)
    ideals = [(marks * w) / total_weight for w in dec_weights]

    # base_i = floor(ideal_i / step) * step
    bases = [((ideal / step).quantize(Decimal("1"), rounding=ROUND_FLOOR)) * step for ideal in ideals]
    remainder = marks - sum(bases)

    # Number of step increments to distribute
    steps_to_give = int((remainder / step).quantize(Decimal("1")))

    # Differences: ideal_i - base_i
    # Ties broken by: larger weight, then lower index (stable sort)
    diffs = [
        (ideals[i] - bases[i], dec_weights[i], -i, i)
        for i in range(n)
    ]
    # Sort descending by difference, weight, and lower index
    diffs.sort(reverse=True)

    result = list(bases)
    for k in range(steps_to_give):
        idx = diffs[k % n][3]
        result[idx] += step

    assert sum(result) == marks, f"Sum invariant broken: got {sum(result)}, expected {marks}"
    return result
