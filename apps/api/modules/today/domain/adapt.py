"""The adaptive budget rule (FR-F13-37), pure: three answers in a row of "too much" (or "too little") suggest 15 percent fewer (or more) minutes."""

from __future__ import annotations

from collections.abc import Sequence

from .constants import ADAPT_PCT, FEEDBACK_STREAK, SETTING_MINUTES_MAX, SETTING_MINUTES_MIN


def suggested_minutes(current: int, direction: str) -> int:
    """`current` changed by 15 percent, rounded to the nearest 5 (half up) and kept inside the settings range."""
    pct = 100 - ADAPT_PCT if direction == "too_much" else 100 + ADAPT_PCT
    rounded = ((current * pct + 250) // 500) * 5
    return max(SETTING_MINUTES_MIN, min(SETTING_MINUTES_MAX, rounded))


def suggestion(ratings_newest_first: Sequence[str], current: int) -> dict | None:
    """`{direction, minutes, current}` when the last `FEEDBACK_STREAK` unused answers are all the same extreme and the minutes would change."""
    latest = list(ratings_newest_first[:FEEDBACK_STREAK])
    if len(latest) < FEEDBACK_STREAK or len(set(latest)) != 1 or latest[0] == "just_right":
        return None
    minutes = suggested_minutes(current, latest[0])
    if minutes == current:
        return None
    return {"direction": latest[0], "minutes": minutes, "current": current}
