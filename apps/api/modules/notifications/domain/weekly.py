"""
The weekly summary in time and in substance (X-01.1 W3.5, FR-N13): when it is next due, which week it covers, and
whether a week is worth an email. Pure: `now`, the time zone and every count come in as arguments.

It is sent on Sunday at 18:00 in the student's own time zone and looks back over the seven local days that end on
that Sunday. A week with no study time, no streak, and nothing due for revision is skipped (an empty email is noise).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from enum import StrEnum
from zoneinfo import ZoneInfo

from .catalogue import get_event

WEEKLY_WEEKDAY = 6  # Monday is 0, so Sunday is 6
WEEKLY_TIME = time(18, 0)
WINDOW_DAYS = 7


def _candidate(day: date, tz: ZoneInfo) -> datetime:
    return datetime.combine(day, WEEKLY_TIME, tzinfo=tz).astimezone(UTC)


def next_weekly_at(now: datetime, tz_name: str) -> datetime:
    """UTC instant of the next Sunday 18:00 (local) strictly after `now`."""
    if now.tzinfo is None:
        raise ValueError("`now` must be timezone-aware")
    tz = ZoneInfo(tz_name)
    today = now.astimezone(tz).date()
    day = today + timedelta(days=(WEEKLY_WEEKDAY - today.weekday()) % 7)
    candidate = _candidate(day, tz)
    if candidate <= now:
        candidate = _candidate(day + timedelta(days=7), tz)
    return candidate


def schedule_weekly(*, now: datetime, enabled: bool, tz_name: str) -> datetime | None:
    """What `next_weekly_at` should hold: the next due instant, or None when the student wants no weekly email."""
    return next_weekly_at(now, tz_name) if enabled else None


def weekly_local_date(due_at: datetime, tz_name: str) -> date:
    """The student's local day a weekly summary belongs to: the day of its due time, even when the sweep is late."""
    if due_at.tzinfo is None:
        raise ValueError("`due_at` must be timezone-aware")
    return due_at.astimezone(ZoneInfo(tz_name)).date()


def week_window(local_day: date) -> tuple[date, date]:
    """First and last local day (both inclusive) of the seven days that end on `local_day`."""
    return local_day - timedelta(days=WINDOW_DAYS - 1), local_day


def iso_week_key(local_day: date) -> str:
    """`2026-W41`: the idempotency part of the weekly event, one per student per ISO week."""
    year, week, _ = local_day.isocalendar()
    return f"{year}-W{week:02d}"


@dataclass(frozen=True)
class WeeklyFacts:
    study_seconds: int
    active_days: int
    streak_days: int
    coverage_pct: float | None  # None when the student has no enrolment
    due_for_revision: int
    days_to_exam: int | None  # None when no exam date is set or it has passed


def worth_sending(facts: WeeklyFacts) -> bool:
    """A week with no study time and nothing due is skipped. A streak alone cannot exist without study time."""
    return facts.study_seconds > 0 or facts.due_for_revision > 0


class WeeklyVerdict(StrEnum):
    SEND = "send"
    STALE = "stale"  # overdue by more than the summary stays useful (the sweep was down): skip, plan the next one


def max_lateness() -> timedelta:
    return get_event("weekly_summary").expires_after or timedelta(0)


def judge_weekly(*, now: datetime, due_at: datetime) -> WeeklyVerdict:
    return WeeklyVerdict.STALE if now - due_at > max_lateness() else WeeklyVerdict.SEND
