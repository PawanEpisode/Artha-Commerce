"""Student notification settings: validated writes, and the next-nudge instant that depends on them."""

from __future__ import annotations

from datetime import datetime, time
from typing import Any

from django.db import transaction
from django.utils import timezone

from ..domain.nudge import schedule_nudge
from ..domain.quiet_hours import is_valid_timezone
from ..domain.weekly import next_weekly_at
from ..errors import InvalidSettings
from ..models import NotificationSettings

EDITABLE = (
    "push_master",
    "timezone",
    "quiet_enabled",
    "quiet_start",
    "quiet_end",
    "nudge_enabled",
    "nudge_time",
    "nudge_tone",
)
#: Changing any of these moves the next nudge.
_NUDGE_INPUTS = {"push_master", "timezone", "nudge_enabled", "nudge_time"}


def _refresh_next_weekly(row: NotificationSettings, now: datetime) -> None:
    """The weekly email follows the student's time zone only. Whether it is wanted is judged when it falls due."""
    row.next_weekly_at = next_weekly_at(now, row.timezone)


def ensure_next_weekly(row: NotificationSettings, now: datetime) -> bool:
    """A row without a weekly time gets one. Changes the row in memory only; the caller saves."""
    if row.next_weekly_at is not None:
        return False
    _refresh_next_weekly(row, now)
    return True


def backfill_next_weekly(now: datetime, *, limit: int) -> int:
    """Self-healing for rows that predate the weekly email: give up to `limit` of them their first Sunday."""
    done = 0
    pending = NotificationSettings.objects.filter(next_weekly_at__isnull=True).order_by("created_at")[:limit]
    for row in list(pending):
        if not ensure_next_weekly(row, now):
            continue
        done += NotificationSettings.objects.filter(pk=row.pk, next_weekly_at__isnull=True).update(
            next_weekly_at=row.next_weekly_at, updated_at=timezone.now()
        )
    return done


def get_or_create_row(user_id) -> NotificationSettings:
    row, _ = NotificationSettings.objects.get_or_create(user_id=user_id)
    return row


def _refresh_next_nudge(row: NotificationSettings, now: datetime) -> None:
    row.next_nudge_at = schedule_nudge(
        now=now,
        enabled=row.nudge_enabled,
        master_on=row.push_master,
        tz_name=row.timezone,
        nudge_time=row.nudge_time,
    )


def ensure_next_nudge(row: NotificationSettings, now: datetime) -> bool:
    """
    A row that wants a nudge but has no time yet (created by the permission journey, which does not touch the nudge
    settings) gets its first one. Changes the row in memory only; the caller saves. True when it set one.
    """
    if row.next_nudge_at is not None or not (row.nudge_enabled and row.push_master):
        return False
    _refresh_next_nudge(row, now)
    return True


def backfill_next_nudges(now: datetime, *, limit: int) -> int:
    """
    Self-healing for rows that predate `ensure_next_nudge` (or were written by hand): give up to `limit` of them their
    first nudge time. A compare-and-set per row, so a student who changes their settings at the same moment wins.
    """
    done = 0
    pending = NotificationSettings.objects.filter(
        nudge_enabled=True, push_master=True, next_nudge_at__isnull=True
    ).order_by("created_at")[:limit]
    for row in list(pending):
        if not ensure_next_nudge(row, now):
            continue
        done += NotificationSettings.objects.filter(pk=row.pk, next_nudge_at__isnull=True).update(
            next_nudge_at=row.next_nudge_at, updated_at=timezone.now()
        )
    return done


def update_settings(user_id, changes: dict[str, Any], *, now: datetime | None = None) -> NotificationSettings:
    """Apply a partial change. Raises `InvalidSettings` (field -> message in `extra`) and writes nothing on error."""
    now = now or timezone.now()
    unknown = sorted(set(changes) - set(EDITABLE))
    if unknown:
        raise InvalidSettings(extra={field: ["Unknown field."] for field in unknown})
    with transaction.atomic():
        row = NotificationSettings.objects.select_for_update().filter(user_id=user_id).first()
        if row is None:
            row = NotificationSettings(user_id=user_id)
        for field, value in changes.items():
            setattr(row, field, value)
        _validate(row)
        if row._state.adding or _NUDGE_INPUTS & set(changes):
            _refresh_next_nudge(row, now)
        else:
            ensure_next_nudge(row, now)
        if row._state.adding or "timezone" in changes:
            _refresh_next_weekly(row, now)
        else:
            ensure_next_weekly(row, now)
        row.save()
    return row


def _validate(row: NotificationSettings) -> None:
    errors: dict[str, list[str]] = {}
    if not is_valid_timezone(row.timezone):
        errors["timezone"] = ["Unknown time zone."]
    if not isinstance(row.quiet_start, time) or not isinstance(row.quiet_end, time):
        errors["quiet_start"] = ["Use a time of day."]
    elif row.quiet_start == row.quiet_end:
        errors["quiet_end"] = ["Quiet hours must start and end at different times."]
    if errors:
        raise InvalidSettings(extra=errors)
