"""Request parsing and response shapes. No rules beyond shape; services validate meaning."""

from __future__ import annotations

from django.utils import timezone
from rest_framework import serializers

from .domain import enums
from .domain.catalogue import CATEGORIES
from .domain.enums import choices
from .domain.followup import followup_due
from .services.settings import EDITABLE


class SettingsWriteSerializer(serializers.Serializer):
    """Any subset of the editable fields (PUT is a partial update, so each toggle can save on its own)."""

    push_master = serializers.BooleanField(required=False)
    timezone = serializers.CharField(required=False, max_length=64)
    quiet_enabled = serializers.BooleanField(required=False)
    quiet_start = serializers.TimeField(required=False)
    quiet_end = serializers.TimeField(required=False)
    nudge_enabled = serializers.BooleanField(required=False)
    nudge_time = serializers.TimeField(required=False)
    nudge_tone = serializers.ChoiceField(required=False, choices=choices(enums.Tone))

    def validate(self, attrs):
        unknown = sorted(set(self.initial_data) - set(EDITABLE))
        if unknown:
            raise serializers.ValidationError({field: ["Unknown field."] for field in unknown})
        return attrs


class PreferenceItemSerializer(serializers.Serializer):
    category = serializers.ChoiceField(choices=[c.key.value for c in CATEGORIES])
    channel = serializers.ChoiceField(choices=choices(enums.Channel))
    enabled = serializers.BooleanField()


class PreferencesWriteSerializer(serializers.Serializer):
    preferences = PreferenceItemSerializer(many=True, allow_empty=False, max_length=60)


class PermissionStateSerializer(serializers.Serializer):
    state = serializers.ChoiceField(choices=choices(enums.PermissionState))
    source = serializers.ChoiceField(choices=choices(enums.PermissionSource))


class SubscriptionKeysSerializer(serializers.Serializer):
    p256dh = serializers.CharField(max_length=256)
    auth = serializers.CharField(max_length=256)


class SubscriptionSerializer(serializers.Serializer):
    """The browser's `PushSubscription.toJSON()`. Meaning (host allow-list, key shape) is checked by the service."""

    endpoint = serializers.CharField(max_length=2048)
    keys = SubscriptionKeysSerializer()


class DeviceRegisterSerializer(serializers.Serializer):
    """`label` from older clients is accepted and ignored: the label is derived on the server from closed sets."""

    subscription = SubscriptionSerializer()
    platform = serializers.ChoiceField(choices=choices(enums.DevicePlatform), default=enums.DevicePlatform.OTHER)
    browser = serializers.ChoiceField(choices=choices(enums.DeviceBrowser), default=enums.DeviceBrowser.OTHER)
    display_mode = serializers.ChoiceField(choices=choices(enums.DisplayMode), default=enums.DisplayMode.BROWSER)
    sw_version = serializers.CharField(required=False, allow_blank=True, allow_null=True, max_length=16)


def device_dict(row: dict) -> dict:
    """One entry of the device list (the selector already left the secrets out)."""
    return {
        "id": str(row["id"]),
        "label": row["label"],
        "platform": row["platform"],
        "browser": row["browser"],
        "display_mode": row["display_mode"],
        "last_seen_at": row["last_seen_at"].isoformat(),
        "created_at": row["created_at"].isoformat(),
    }


def _hhmm(value) -> str:
    return value.strftime("%H:%M")


def settings_dict(row) -> dict:
    return {
        "push_master": row.push_master,
        "timezone": row.timezone,
        "quiet_enabled": row.quiet_enabled,
        "quiet_start": _hhmm(row.quiet_start),
        "quiet_end": _hhmm(row.quiet_end),
        "nudge_enabled": row.nudge_enabled,
        "nudge_time": _hhmm(row.nudge_time),
        "nudge_tone": row.nudge_tone,
        "permission_state": row.permission_state,
        "permission_decided": row.permission_decided_at is not None,
        "permission_ask_count": row.permission_ask_count,
        "last_asked_at": row.last_asked_at.isoformat() if row.last_asked_at else None,
        # May the page show a follow-up ask now? The server owns the spacing and the cap (domain/followup.py).
        "followup_due": followup_due(
            row.permission_state,
            row.permission_ask_count,
            row.last_asked_at,
            row.permission_decided_at,
            timezone.now(),
        ),
    }
