"""Student notification settings: validated writes, and the next-nudge instant that depends on them."""

from __future__ import annotations

from datetime import datetime, time
from typing import Any

from django.db import transaction
from django.utils import timezone

from ..domain.nudge import next_nudge_at
from ..domain.quiet_hours import is_valid_timezone
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


def get_or_create_row(user_id) -> NotificationSettings:
    row, _ = NotificationSettings.objects.get_or_create(user_id=user_id)
    return row


def _refresh_next_nudge(row: NotificationSettings, now: datetime) -> None:
    due = row.nudge_enabled and row.push_master
    row.next_nudge_at = next_nudge_at(now, row.timezone, row.nudge_time) if due else None


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
        if row._state.adding or _NUDGE_INPUTS & set(changes) or (row.nudge_enabled and row.next_nudge_at is None):
            _refresh_next_nudge(row, now)
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
