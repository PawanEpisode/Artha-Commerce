"""Gates of the notifications module: the environment master switch and the PostHog flags."""

from django.conf import settings

from core.feature_flags import flag_enabled

#: Student-facing surfaces (settings, onboarding step, bell).
UI_FLAG = "notifications_ui"
#: Anything that sends. Strict: PostHog being unreachable means off.
SEND_FLAG = "notifications_send"


def master_enabled() -> bool:
    return bool(getattr(settings, "NOTIFICATIONS_ENABLED", False))


def ui_enabled(user_id) -> bool:
    """Show the settings and permission surfaces: the environment switch AND the (non-strict) UI flag."""
    return master_enabled() and flag_enabled(UI_FLAG, user_id)


def send_flag_enabled(user_id) -> bool:
    """The PostHog sending flag alone, strict: only an explicit `on` counts."""
    return flag_enabled(SEND_FLAG, user_id, strict=True)


def sending_enabled(user_id) -> bool:
    """Allowed to send: the environment switch AND an explicit `on` from PostHog (fails closed)."""
    return master_enabled() and send_flag_enabled(user_id)


def event_disabled(event_key: str) -> bool:
    """Ops kill switch for one event type (`NOTIFICATIONS_DISABLED_EVENTS`, comma separated)."""
    return event_key in set(getattr(settings, "NOTIFICATIONS_DISABLED_EVENTS", ()) or ())


def declarative_push_enabled() -> bool:
    """FR-N35: add Safari's declarative fields to each push. Off until the Safari spike (S3) has passed on a device."""
    return bool(getattr(settings, "NOTIFICATIONS_DECLARATIVE_PUSH", False)) and bool(
        getattr(settings, "NOTIFICATIONS_WEB_BASE_URL", "")
    )
