"""Reads for the fatigue control (X-01.1 W3.7): the student's recent pushes and whether the digest offer is due."""

from __future__ import annotations

from datetime import datetime

from django.utils import timezone

from ..domain import fatigue
from ..domain.enums import Channel, DeliveryStatus
from ..models import Delivery
from .settings import get_settings

#: Enough delivery rows to find five distinct notifications for a student with a few devices.
_ROWS = 50


def recent_pushes(user_id, *, limit: int = fatigue.RUN_LENGTH) -> list[fatigue.PushFact]:
    """
    The student's last `limit` pushes that count towards the cap, newest first, one per notification. Reads the
    `notif_delivery_sent_idx` index (student, newest first, sent only).
    """
    rows = (
        Delivery.objects.filter(
            user_id=user_id, status=DeliveryStatus.SENT, channel=Channel.PUSH, counts_toward_cap=True
        )
        .order_by("-attempted_at")
        .values_list("notification_id", "attempted_at", "clicked_at")[:_ROWS]
    )
    seen: dict[object, fatigue.PushFact] = {}
    for notification_id, attempted_at, clicked_at in rows:
        fact = seen.get(notification_id)
        if fact is None:
            if len(seen) == limit:
                break
            seen[notification_id] = fatigue.PushFact(attempted_at, clicked_at is not None)
        elif clicked_at is not None and not fact.clicked:  # a click on any device counts for the notification
            seen[notification_id] = fatigue.PushFact(fact.sent_at, True)
    return list(seen.values())


def digest_offer_due(user_id, *, now: datetime | None = None) -> bool:
    row = get_settings(user_id)
    return fatigue.should_offer(
        recent_pushes(user_id),
        offered_at=row.digest_offered_at,
        digest_on=row.digest_enabled,
        now=now or timezone.now(),
        tz=row.timezone,
    )
