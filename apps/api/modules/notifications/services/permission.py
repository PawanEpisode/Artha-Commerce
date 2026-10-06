"""The browser permission journey: what the student was shown and what they decided (a consent record)."""

from __future__ import annotations

from datetime import datetime

from django.db import transaction
from django.utils import timezone

from ..domain.enums import DECIDED_STATES, PermissionSource, PermissionState
from ..domain.followup import MAX_ASKS, followup_due
from ..errors import InvalidSettings
from ..models import NotificationSettings


def record_permission_state(user_id, state: str, source: str, *, now: datetime | None = None) -> NotificationSettings:
    """
    Record a state reported by the page. Showing our own pre-prompt counts as an ask (capped, so the follow-up rule stays
    bounded); any decided state stamps `permission_decided_at`. Repeating the same state is harmless.

    A student who already decided is never moved back to "undecided" by a pre-prompt: the onboarding step and the setup
    card read the decision as a fact. Only an eligible follow-up (see `domain.followup`) counts as a new ask, and it
    leaves the stored state alone until the student answers it. The 14 day spacing is enforced here, not in the page.
    """
    now = now or timezone.now()
    try:
        new_state = PermissionState(state)
        new_source = PermissionSource(source)
    except ValueError:
        raise InvalidSettings("Unknown permission state or source.") from None
    with transaction.atomic():
        row, _ = NotificationSettings.objects.select_for_update().get_or_create(user_id=user_id)
        if new_state is PermissionState.PRE_PROMPT_SHOWN:
            if PermissionState(row.permission_state) in DECIDED_STATES:
                due = new_source is PermissionSource.FOLLOWUP and followup_due(
                    row.permission_state, row.permission_ask_count, row.last_asked_at, row.permission_decided_at, now
                )
                if due:
                    row.permission_ask_count = min(row.permission_ask_count + 1, MAX_ASKS)
                    row.last_asked_at = now
                    row.save()
                return row
            if row.permission_state != new_state:
                row.permission_ask_count = min(row.permission_ask_count + 1, MAX_ASKS)
                row.last_asked_at = now
        if new_state in DECIDED_STATES:
            row.permission_decided_at = now
        row.permission_state = new_state
        row.permission_source = new_source
        row.save()
    return row
