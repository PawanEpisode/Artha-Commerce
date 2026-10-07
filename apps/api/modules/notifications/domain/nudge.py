"""
The daily nudge in time (X-01.1 W3.3, FR-N10): when it is next due, which local day it belongs to, and whether a due
nudge is still worth sending. Pure: `now` and the time zone come in as arguments.

Daylight saving is handled by `zoneinfo`, not by hand. Two rules follow from how a local wall time maps to an instant:
a nudge time that does not exist on the day the clocks go forward (02:30 in New York on 8 March) is sent at the first
moment after the gap (03:30), and one that happens twice on the day they go back (01:30) is sent at its first
occurrence only, because "strictly after now" never picks the repeated hour a second time.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from enum import StrEnum
from zoneinfo import ZoneInfo

from .catalogue import get_event


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


def schedule_nudge(*, now: datetime, enabled: bool, master_on: bool, tz_name: str, nudge_time: time) -> datetime | None:
    """What `next_nudge_at` should hold for these settings: the next due instant, or None when no nudge is wanted."""
    if not (enabled and master_on):
        return None
    return next_nudge_at(now, tz_name, nudge_time)


def nudge_local_date(due_at: datetime, tz_name: str) -> date:
    """The student's local day a nudge belongs to: the day of its due time, even when the sweep runs a little late."""
    if due_at.tzinfo is None:
        raise ValueError("`due_at` must be timezone-aware")
    return due_at.astimezone(ZoneInfo(tz_name)).date()


class NudgeVerdict(StrEnum):
    SEND = "send"
    STALE = "stale"  # overdue by more than the nudge stays useful (the sweep was down): skip it and plan the next one


def max_lateness() -> timedelta:
    """How late a nudge may still go out: as long as the catalogue says the notification stays useful."""
    return get_event("daily_nudge").expires_after or timedelta(0)


def judge_nudge(*, now: datetime, due_at: datetime) -> NudgeVerdict:
    """Read-only: is a nudge that fell due at `due_at` still worth sending at `now`?"""
    return NudgeVerdict.STALE if now - due_at > max_lateness() else NudgeVerdict.SEND
