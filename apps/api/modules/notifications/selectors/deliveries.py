from __future__ import annotations

from datetime import datetime

from ..domain.enums import Channel, DeliveryStatus
from ..models import Delivery


def sent_cap_count(user_id, start: datetime, end: datetime, *, exclude_notification_id=None) -> int:
    """
    Distinct notifications pushed to the student in [start, end) that count towards the daily cap. Counted per
    notification, not per row: a student with three phones who got one alert has used one slot. A notification being
    retried is excluded so it never blocks itself.
    """
    rows = Delivery.objects.filter(
        user_id=user_id,
        channel=Channel.PUSH,
        status=DeliveryStatus.SENT,
        counts_toward_cap=True,
        attempted_at__gte=start,
        attempted_at__lt=end,
    )
    if exclude_notification_id is not None:
        rows = rows.exclude(notification_id=exclude_notification_id)
    return rows.values("notification_id").distinct().count()
