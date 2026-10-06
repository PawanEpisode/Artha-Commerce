"""Inbox writes: the click a deep link reports (W2.3) and marking items read from the inbox (W3.1). Reads: selectors/inbox.py."""

from __future__ import annotations

from datetime import datetime

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import NotFound

from ..domain.enums import DeliveryStatus
from ..models import Delivery, Notification
from ..selectors import inbox as inbox_selectors


def mark_clicked(user_id, notification_id, *, now: datetime | None = None) -> None:
    """
    The student opened the app from a notification (`?n=<id>`): mark it read and its pushes clicked. Only the student's
    own notification counts (another's, or an unknown id, is a 404). Idempotent: a repeat keeps the first timestamps.
    The click does not say which device it came from, so every push already sent for this notification is marked.
    """
    now = now or timezone.now()
    with transaction.atomic():
        notification = Notification.objects.select_for_update().filter(id=notification_id, user_id=user_id).first()
        if notification is None:
            raise NotFound("Notification not found.")
        if notification.read_at is None:
            notification.read_at = now
            notification.save(update_fields=["read_at", "updated_at"])
        Delivery.objects.filter(
            notification=notification, user_id=user_id, status=DeliveryStatus.SENT, clicked_at__isnull=True
        ).update(clicked_at=now, updated_at=timezone.now())


def mark_read(user_id, *, ids: list | None = None, now: datetime | None = None) -> int:
    """
    Mark the student's visible unread notifications read: the given ids, or every one when `ids` is None. Ids that
    are unknown, already read, hidden, or someone else's are skipped without a word, so the answer never reveals
    whether another student's id exists. Idempotent: a repeat changes nothing and keeps the first timestamp.
    Returns how many rows changed.
    """
    now = now or timezone.now()
    rows = inbox_selectors.visible(user_id, now=now).filter(read_at__isnull=True)
    if ids is not None:
        rows = rows.filter(id__in=ids)
    return rows.update(read_at=now, updated_at=timezone.now())
