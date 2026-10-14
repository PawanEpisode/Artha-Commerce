"""
Tracking adapter (F-04). The only Today file that imports `modules.tracking`: the student's time zone (read only, a student with
no tracker row gets the default and nothing is written) and the days on which tracked time exists.
"""

from __future__ import annotations

from datetime import date

from modules.tracking import selectors as tracking
from modules.tracking.domain import durations


def timezone_of(user_id) -> str:
    return tracking.settings_or_default(user_id).tz


def local_date(moment, tz: str) -> date:
    return durations.local_date(moment, tz)


def days_with_time(user_id, start: date, end: date) -> set[date]:
    return set(tracking.day_totals(user_id, start, end))


def streak_and_goal(user_id, today: date) -> tuple[int, dict]:
    """The tracker's streak and today's daily goal (`target_minutes`, `done_seconds`, `percent`). Today never computes its own."""
    progress = tracking.goals_progress(user_id, today)
    daily = progress["daily"]
    goal = {k: daily[k] for k in ("target_minutes", "done_seconds", "percent")}
    return progress["streak"], goal
