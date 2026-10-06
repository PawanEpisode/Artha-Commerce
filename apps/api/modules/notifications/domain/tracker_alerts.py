"""
When the tracker alerts happen (X-01.1 W3.2). Pure functions of plain values: no Django, no clock, no I/O.

* A long stopwatch is announced once its counted time reaches `STOPWATCH_LONG_AFTER`.
* A streak at risk is announced `STREAK_LEAD` before the student's day ends. The day ends at local midnight, or earlier
  when the student's quiet hours begin in the evening, because a student who goes quiet at 22:00 is not studying after
  it and a message inside the quiet window would only be held and dropped.
"""

from __future__ import annotations

from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

from .policy import QuietPreference
from .quiet_hours import in_quiet_hours

STOPWATCH_LONG_AFTER = timedelta(hours=3)
STREAK_LEAD = timedelta(minutes=90)
#: No streak alert before this local time, so the sweep only looks at the evening and a quiet-hours start in the
#: afternoon cannot pull the alert into working hours.
STREAK_EARLIEST_LOCAL = time(16, 0)


def stopwatch_long_after_seconds() -> int:
    return int(STOPWATCH_LONG_AFTER.total_seconds())


def _evening_begins(local_date, tracker_tz: str) -> datetime:
    return datetime.combine(local_date, STREAK_EARLIEST_LOCAL, tzinfo=ZoneInfo(tracker_tz)).astimezone(UTC)


def day_end(local_date, tracker_tz: str, quiet: QuietPreference | None) -> datetime:
    """
    The instant (UTC) the student's day ends: local midnight, or the start of the quiet window that covers the late evening
    when that is earlier. If the student is already quiet when the evening begins, the day ends then (no evening is left).
    """
    tz = ZoneInfo(tracker_tz)
    evening = _evening_begins(local_date, tracker_tz)
    end = datetime.combine(local_date + timedelta(days=1), time.min, tzinfo=tz).astimezone(UTC)
    if quiet is None or not quiet.enabled:
        return end
    if in_quiet_hours(evening, quiet.timezone, quiet.start, quiet.end):
        return evening
    if quiet.start > quiet.end:  # an overnight window: it begins in the evening and ends the day
        quiet_tz = ZoneInfo(quiet.timezone)
        first = evening.astimezone(quiet_tz).date()
        for day in (first, first + timedelta(days=1)):
            begins = datetime.combine(day, quiet.start, tzinfo=quiet_tz).astimezone(UTC)
            if evening <= begins < end:
                end = min(end, begins)
    return end


def streak_window(local_date, tracker_tz: str, quiet: QuietPreference | None) -> tuple[datetime, datetime] | None:
    """
    The span (UTC, start inclusive, end exclusive) in which a streak alert for `local_date` may be created, or None when
    the student's day ends too early for one. It opens `STREAK_LEAD` before the day ends but never before
    `STREAK_EARLIEST_LOCAL`.
    """
    end = day_end(local_date, tracker_tz, quiet)
    start = max(end - STREAK_LEAD, _evening_begins(local_date, tracker_tz))
    return (start, end) if start < end else None
