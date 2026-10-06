from __future__ import annotations

from datetime import datetime

from django.utils import timezone

from ..domain.enums import DECIDED_STATES
from ..domain.followup import followup_due as _followup_due
from ..models import NotificationSettings


def get_settings(user_id) -> NotificationSettings:
    """The student's row, or an unsaved one carrying the defaults. Reading never writes."""
    return NotificationSettings.objects.filter(user_id=user_id).first() or NotificationSettings(user_id=user_id)


def permission_decided(user_id) -> bool:
    """True once the student decided (any outcome). Used by the onboarding step in `profiles`."""
    return NotificationSettings.objects.filter(
        user_id=user_id, permission_state__in=[s.value for s in DECIDED_STATES]
    ).exists()


def followup_due(user_id, now: datetime | None = None) -> bool:
    """True when the student said "Not now" earlier and may be asked once more (W2.5b). Reading never writes."""
    row = get_settings(user_id)
    return _followup_due(
        row.permission_state,
        row.permission_ask_count,
        row.last_asked_at,
        row.permission_decided_at,
        now or timezone.now(),
    )
