"""The student's recall settings row, created on first read. W5 and later waves add the settings endpoint on top of it."""

from __future__ import annotations

from ..models import RecallSettings


def settings_for(user_id) -> RecallSettings:
    row, _ = RecallSettings.objects.get_or_create(user_id=user_id)
    return row


def study_clock(user_id) -> tuple[str, int]:
    """`(time zone, day-start hour)` that define the student's study day."""
    row = settings_for(user_id)
    return row.tz, row.day_start_hour
