from __future__ import annotations

from ..models import Device, Notification, NotificationSettings, Preference


def export_all(user_id) -> dict:
    """Everything held for the student, with no secrets (device keys and endpoints are never exported)."""
    settings = NotificationSettings.objects.filter(user_id=user_id).values().first()
    return {
        "settings": settings,
        "preferences": list(Preference.objects.filter(user_id=user_id).values("category", "channel", "enabled")),
        "devices": list(
            Device.objects.filter(user_id=user_id).values(
                "kind", "platform", "browser", "display_mode", "label", "last_seen_at", "revoked_at", "created_at"
            )
        ),
        "notifications": list(
            Notification.objects.filter(user_id=user_id)
            .order_by("-created_at")
            .values("event", "category", "title", "body", "deep_link", "read_at", "created_at")[:500]
        ),
    }
