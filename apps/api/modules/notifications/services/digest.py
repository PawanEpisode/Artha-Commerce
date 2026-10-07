"""
The daily digest switch (X-01.1 W3.7, FR-N34). Writes only: the offer being seen or answered, and switching the digest
on or off. Reads are `selectors.fatigue`; what the digest says is `domain.digest`; sending it is the daily slot
(`services.nudge`).

Accepting switches the push channel off and the inbox on for every category except the timer, turns the digest on, and
makes sure the daily slot is planned (the digest goes out at the nudge time). Switching it off again stops the digest
and puts those push switches back to their defaults, so the student is where they were before the offer (a category
they had switched off themselves before accepting is turned back on; they can switch it off again).
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from django.db import transaction
from django.utils import timezone

from ..domain.catalogue import CATEGORIES
from ..domain.digest import KEEP_PUSH
from ..domain.enums import Channel
from ..models import NotificationSettings
from ..selectors import fatigue as fatigue_selectors
from . import preferences
from . import settings as settings_service


class Answer(StrEnum):
    SEEN = "seen"  # the card was shown: counts as the offer for this 30-day period
    ACCEPT = "accept"
    DECLINE = "decline"
    STOP = "stop"  # back to separate alerts (from the settings page, any time)


def _push_categories() -> list[str]:
    return [
        spec.key.value for spec in CATEGORIES if Channel.PUSH in spec.default_channels and spec.key not in KEEP_PUSH
    ]


def answer(user_id, choice: Answer, *, now: datetime | None = None) -> NotificationSettings:
    """Record what the student did with the offer, or switch the digest on or off. Each answer is safe to repeat."""
    now = now or timezone.now()
    with transaction.atomic():
        settings_service.get_or_create_row(user_id)
        row = NotificationSettings.objects.select_for_update().get(pk=user_id)
        if choice is Answer.SEEN:
            if fatigue_selectors.digest_offer_due(user_id, now=now):
                row.digest_offered_at = now
                row.save(update_fields=["digest_offered_at", "updated_at"])
            return row
        if choice is Answer.DECLINE:
            row.digest_offered_at = now
            row.save(update_fields=["digest_offered_at", "updated_at"])
            return row
        categories = _push_categories()
        if choice is Answer.ACCEPT:
            preferences.set_preferences(
                user_id,
                [(c, Channel.PUSH.value, False) for c in categories]
                + [(c, Channel.INBOX.value, True) for c in categories],
            )
            row.digest_enabled, row.digest_offered_at = True, now
            row.save(update_fields=["digest_enabled", "digest_offered_at", "updated_at"])
            # The digest rides the daily slot, so the slot must be on and planned.
            return settings_service.update_settings(user_id, {"nudge_enabled": True}, now=now)
        preferences.set_preferences(user_id, [(c, Channel.PUSH.value, True) for c in categories])
        row.digest_enabled = False
        row.save(update_fields=["digest_enabled", "updated_at"])
        return row
