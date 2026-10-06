"""When the next daily nudge is due: the student's chosen local time, on the next local day it has not passed."""

from __future__ import annotations

from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo


def next_nudge_at(now: datetime, tz_name: str, nudge_time: time) -> datetime:
    """UTC instant of the next occurrence of `nudge_time` (local) strictly after `now`."""
    if now.tzinfo is None:
        raise ValueError("`now` must be timezone-aware")
    tz = ZoneInfo(tz_name)
    today = now.astimezone(tz).date()
    candidate = datetime.combine(today, nudge_time, tzinfo=tz).astimezone(UTC)
    if candidate <= now:
        candidate = datetime.combine(today + timedelta(days=1), nudge_time, tzinfo=tz).astimezone(UTC)
    return candidate
