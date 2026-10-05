"""
Pure report maths: period bucketing, compare ranges, pace and heatmap intensity. No Django. The web mirrors the
heatmap buckets in `modules/tracker/lib/heatmap.ts` (parity test) and the range helpers in `lib/range.ts`.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

GROUPS = ("day", "week", "month")
MAX_DAYS_DAY_GROUP = 366
MAX_DAYS_OTHER_GROUPS = 5 * 366
HOURS_DEFAULT_DAYS = 90

# Heatmap intensity: 0 = nothing, 1 = under 30 min, 2 = 30 to under 90, 3 = 90 to under 180, 4 = 180 to under 300, 5 = 300+
HEATMAP_EDGES_SECONDS = (1, 30 * 60, 90 * 60, 180 * 60, 300 * 60)

PACE_TOLERANCE_SECONDS = 15 * 60
LOW_COVERAGE_PCT = 40


class RangeError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def intensity(seconds: int) -> int:
    """Heatmap bucket for a day's seconds (0..5)."""
    level = 0
    for edge in HEATMAP_EDGES_SECONDS:
        if seconds >= edge:
            level += 1
    return level


def week_start_of(day: date, week_start: int = 1) -> date:
    """First day of the week containing `day`. `week_start`: 1 = Monday, 0 = Sunday."""
    back = day.weekday() if week_start == 1 else (day.weekday() + 1) % 7
    return day - timedelta(days=back)


def _next_month(day: date) -> date:
    return date(day.year + (day.month == 12), day.month % 12 + 1, 1)


def bucket_start(day: date, group: str, week_start: int = 1) -> date:
    if group == "day":
        return day
    if group == "week":
        return week_start_of(day, week_start)
    if group == "month":
        return day.replace(day=1)
    raise RangeError("bad_group", "Group by day, week or month.")


def bucket_end(start: date, group: str) -> date:
    """Last day (inclusive) of the bucket that begins at `start`."""
    if group == "day":
        return start
    if group == "week":
        return start + timedelta(days=6)
    return _next_month(start) - timedelta(days=1)


@dataclass(frozen=True)
class Bucket:
    start: date
    end: date  # inclusive


def buckets(start: date, end: date, group: str, week_start: int = 1) -> list[Bucket]:
    """Every bucket that touches [start, end], including empty ones, so charts show gaps honestly."""
    out: list[Bucket] = []
    cursor = bucket_start(start, group, week_start)
    while cursor <= end:
        last = bucket_end(cursor, group)
        out.append(Bucket(cursor, last))
        cursor = last + timedelta(days=1)
    return out


def validate_range(start: date, end: date, group: str = "day") -> None:
    if end < start:
        raise RangeError("bad_range", "The end date is before the start date.")
    days = (end - start).days + 1
    limit = MAX_DAYS_DAY_GROUP if group == "day" else MAX_DAYS_OTHER_GROUPS
    if days > limit:
        raise RangeError("range_too_long", f"Pick at most {limit} days for this view.")


def previous_range(start: date, end: date) -> tuple[date, date]:
    """The period of equal length right before [start, end] (compare mode)."""
    length = (end - start).days + 1
    return start - timedelta(days=length), start - timedelta(days=1)


def change(current: int, previous: int) -> dict:
    """Change in seconds and in percent of the previous period (None when there was nothing to compare with)."""
    delta = current - previous
    pct = round(delta * 100 / previous) if previous else None
    return {"seconds": delta, "percent": pct}


def expected_by_today(target_minutes: int, days_before_today: int) -> int:
    """Seconds the student should have by the start of today when the weekly goal is spread evenly over 7 days."""
    return round(target_minutes * 60 * days_before_today / 7)


def pace(done_seconds: int, target_minutes: int, days_before_today: int) -> dict:
    expected = expected_by_today(target_minutes, days_before_today)
    gap = done_seconds - expected
    if gap >= 0:
        state = "ahead" if gap > PACE_TOLERANCE_SECONDS else "on_track"
    else:
        state = "on_track" if -gap <= PACE_TOLERANCE_SECONDS else "behind"
    return {"expected_seconds": expected, "gap_seconds": gap, "state": state}


def chapter_flag(seconds: int, coverage_pct: int, average_seconds: float) -> str:
    """Time versus coverage (FR-28): 'high_time_low_coverage', 'low_time_low_coverage' or ''."""
    if coverage_pct >= LOW_COVERAGE_PCT or average_seconds <= 0:
        return ""
    if seconds >= average_seconds:
        return "high_time_low_coverage"
    if seconds < average_seconds / 2:
        return "low_time_low_coverage"
    return ""


def streak(days_met: set[date], today: date) -> int:
    """Consecutive goal-met days ending today, or ending yesterday while today is still open."""
    cursor = today if today in days_met else today - timedelta(days=1)
    count = 0
    while cursor in days_met:
        count += 1
        cursor -= timedelta(days=1)
    return count
