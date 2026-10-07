"""Account erasure. Registered with `core.registry`; idempotent."""

from __future__ import annotations

from django.db import transaction

from ..models import ActionToken, Device, MessageShown, Notification, NotificationSettings, Preference, ScheduledJob


def delete_all_for_user(user_id) -> dict:
    """Remove everything held for the student. Deliveries go with their notifications (cascade)."""
    with transaction.atomic():
        counts = {
            "action_tokens": ActionToken.objects.filter(user_id=user_id).delete()[0],
            "notifications": Notification.objects.filter(user_id=user_id).delete()[0],
            "devices": Device.objects.filter(user_id=user_id).delete()[0],
            "jobs": ScheduledJob.objects.filter(user_id=user_id).delete()[0],
            "preferences": Preference.objects.filter(user_id=user_id).delete()[0],
            "messages_shown": MessageShown.objects.filter(user_id=user_id).delete()[0],
            "settings": NotificationSettings.objects.filter(user_id=user_id).delete()[0],
        }
    return counts
