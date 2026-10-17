"""
Time-versus-Score diagnosis logic (F-10 PRD 4.7 / FR-F10-24).
Classifies chapters into 4 diagnostic quadrants to identify where more study hours
are NOT the answer (e.g. concept confusion requiring practice, not re-reading).
"""

from __future__ import annotations

from decimal import Decimal
from django.db.models import TextChoices


class TimeVsScoreClass(TextChoices):
    HIGH_TIME_LOW_SCORE = "high_time_low_score", "High time, low score"
    LOW_TIME_LOW_SCORE = "low_time_low_score", "Low time, low score"
    LOW_TIME_HIGH_SCORE = "low_time_high_score", "Low time, high score"
    HIGH_TIME_HIGH_SCORE = "high_time_high_score", "High time, high score"
    NO_DATA = "no_data", "No data"


def diagnose_time_vs_score(
    study_seconds: int,
    accuracy: float | Decimal | None,
    time_threshold_seconds: int,
    accuracy_threshold: float | Decimal = Decimal("0.70"),
    min_answers: int = 5,
    answered_count: int = 0,
) -> TimeVsScoreClass:
    """
    Classifies a chapter into a diagnostic quadrant based on:
    - Time spent studying (tracked seconds) vs benchmark threshold
    - Practice accuracy vs target accuracy threshold
    """
    if answered_count < min_answers and study_seconds == 0:
        return TimeVsScoreClass.NO_DATA

    acc = float(accuracy) if accuracy is not None else 0.0
    acc_thresh = float(accuracy_threshold)

    is_high_time = study_seconds >= time_threshold_seconds
    is_high_score = acc >= acc_thresh

    if is_high_time and not is_high_score:
        return TimeVsScoreClass.HIGH_TIME_LOW_SCORE
    elif not is_high_time and not is_high_score:
        return TimeVsScoreClass.LOW_TIME_LOW_SCORE
    elif not is_high_time and is_high_score:
        return TimeVsScoreClass.LOW_TIME_HIGH_SCORE
    else:
        return TimeVsScoreClass.HIGH_TIME_HIGH_SCORE
