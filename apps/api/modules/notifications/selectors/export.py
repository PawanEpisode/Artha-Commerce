from __future__ import annotations

from django.db.models import F

from ..models import ActionToken, Device, MessageShown, Notification, NotificationSettings, Preference


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
        # Notification buttons made for the student (W3.6): which action, when it expired and whether it was used. The
        # token is never stored, and its hash is not exported.
        "notification_buttons": list(
            ActionToken.objects.filter(user_id=user_id)
            .order_by("-created_at")
            .values("action", "created_at", "expires_at", "used_at")
        ),
        # The daily thoughts the student was given (what the card or the nudge showed, and where it was first used).
        "daily_thoughts": list(
            MessageShown.objects.filter(user_id=user_id)
            .order_by("-shown_on")
            .values("shown_on", "channel", text=F("message__body"))
        ),
    }
