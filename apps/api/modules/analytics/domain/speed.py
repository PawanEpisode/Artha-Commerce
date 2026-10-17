"""
Speed categorization logic for Performance Analytics (F-10).
"""

from __future__ import annotations

from django.db.models import TextChoices


class SpeedFlag(TextChoices):
    FAST_AND_WRONG = "fast_and_wrong", "Fast and wrong"
    SLOW_AND_RIGHT = "slow_and_right", "Slow and right"
    ON_TARGET = "on_target", "On target"
    UNKNOWN = "unknown", "Unknown"


def categorize_speed(
    speed_ratio: float | None,
    is_correct: bool,
) -> SpeedFlag:
    """
    Categorizes answer speed into pedagogical quadrants:
    - Fast and wrong: answered very quickly (<0.85x target) but got it wrong (rushing)
    - Slow and right: got it right but took too long (>1.15x target) (lacks fluency)
    - On target: pace is within standard bounds [0.85x, 1.15x]
    """
    if speed_ratio is None:
        return SpeedFlag.UNKNOWN

    if speed_ratio < 0.85:
        if not is_correct:
            return SpeedFlag.FAST_AND_WRONG
        return SpeedFlag.ON_TARGET

    if speed_ratio > 1.15:
        if is_correct:
            return SpeedFlag.SLOW_AND_RIGHT
        return SpeedFlag.UNKNOWN

    return SpeedFlag.ON_TARGET
