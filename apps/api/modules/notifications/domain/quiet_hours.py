"""
Quiet hours in the student's own time zone. The window may cross midnight (22:00 to 07:00). Start is inclusive and
end is exclusive. Everything takes `now` as an argument so it is deterministic in tests, and uses `zoneinfo` so
daylight-saving changes are handled by the database of zones rather than by hand.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


def is_valid_timezone(name: str) -> bool:
    try:
        ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError, OSError):
        return False
    return True


def _local(now: datetime, tz_name: str) -> datetime:
    if now.tzinfo is None:
        raise ValueError("`now` must be timezone-aware")
    return now.astimezone(ZoneInfo(tz_name))


def local_date(now: datetime, tz_name: str) -> date:
    """The student's calendar date at `now`."""
    return _local(now, tz_name).date()


def local_day_bounds(now: datetime, tz_name: str) -> tuple[datetime, datetime]:
    """Start (inclusive) and end (exclusive) of the student's local day, as UTC instants."""
    tz = ZoneInfo(tz_name)
    day = _local(now, tz_name).date()
    start = datetime.combine(day, time.min, tzinfo=tz)
    end = datetime.combine(day + timedelta(days=1), time.min, tzinfo=tz)
    return start.astimezone(UTC), end.astimezone(UTC)


def in_quiet_hours(now: datetime, tz_name: str, start: time, end: time) -> bool:
    if start == end:
        raise ValueError("Quiet hours need a start and an end that differ")
    at = _local(now, tz_name).time()
    if start < end:
        return start <= at < end
    return at >= start or at < end


def quiet_window_end(now: datetime, tz_name: str, start: time, end: time) -> datetime | None:
    """The UTC instant the current quiet window ends, or None when `now` is outside it."""
    if not in_quiet_hours(now, tz_name, start, end):
        return None
    local = _local(now, tz_name)
    end_day = local.date()
    if start > end and local.time() >= start:
        end_day += timedelta(days=1)
    return datetime.combine(end_day, end, tzinfo=ZoneInfo(tz_name)).astimezone(UTC)
