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


def push_slo_counts(start: datetime, end: datetime, *, max_rows: int = 5000) -> tuple[int, int, list[int]]:
    """
    Push attempts in [start, end): (sent, failed, lateness in ms of the sent ones). Suppressed and queued rows are not
    attempts. The lateness list is capped so a flood cannot make the sweep slow; it keeps the latest rows.
    """
    rows = Delivery.objects.filter(
        channel=Channel.PUSH,
        attempted_at__gte=start,
        attempted_at__lt=end,
        status__in=[DeliveryStatus.SENT, DeliveryStatus.FAILED],
    )
    failed = rows.filter(status=DeliveryStatus.FAILED).count()
    sent_rows = rows.filter(status=DeliveryStatus.SENT)
    sent = sent_rows.count()
    lateness = list(
        sent_rows.exclude(lateness_ms__isnull=True)
        .order_by("-attempted_at")
        .values_list("lateness_ms", flat=True)[:max_rows]
    )
    return sent, failed, lateness
