from __future__ import annotations

from ..domain.enums import DECIDED_STATES
from ..models import NotificationSettings


def get_settings(user_id) -> NotificationSettings:
    """The student's row, or an unsaved one carrying the defaults. Reading never writes."""
    return NotificationSettings.objects.filter(user_id=user_id).first() or NotificationSettings(user_id=user_id)


def permission_decided(user_id) -> bool:
    """True once the student decided (any outcome). Used by the onboarding step in `profiles`."""
    return NotificationSettings.objects.filter(
        user_id=user_id, permission_state__in=[s.value for s in DECIDED_STATES]
    ).exists()
