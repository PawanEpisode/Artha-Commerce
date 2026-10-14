"""Bounds and default estimates per kind of work (PRD Q-F13-12, [VERIFY]). Pure."""

from __future__ import annotations

from .constants import (
    MCQ_SECONDS,
    OWN_EST_MAX,
    OWN_EST_MIN,
    PRACTICAL_SECONDS_PER_MARK,
    PROVIDER_EST_MAX,
    PROVIDER_EST_MIN,
    RECALL_CARD_SECONDS,
)


def valid_estimate(minutes: int, *, own: bool = False) -> bool:
    low, high = (OWN_EST_MIN, OWN_EST_MAX) if own else (PROVIDER_EST_MIN, PROVIDER_EST_MAX)
    return isinstance(minutes, int) and not isinstance(minutes, bool) and low <= minutes <= high


def clamp_estimate(minutes: int, *, own: bool = False) -> int:
    low, high = (OWN_EST_MIN, OWN_EST_MAX) if own else (PROVIDER_EST_MIN, PROVIDER_EST_MAX)
    return max(low, min(high, int(minutes)))


def _minutes(total_seconds: int) -> int:
    return clamp_estimate(-(-total_seconds // 60))  # ceiling, at least one minute


def mcq_minutes(questions: int, seconds_each: int = MCQ_SECONDS) -> int:
    return _minutes(questions * seconds_each)


def recall_minutes(cards: int, seconds_each: int = RECALL_CARD_SECONDS) -> int:
    return _minutes(cards * seconds_each)


def practical_minutes(marks: int, seconds_per_mark: int = PRACTICAL_SECONDS_PER_MARK) -> int:
    return _minutes(marks * seconds_per_mark)
