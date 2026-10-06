"""Request parsing and response shapes. No rules beyond shape; services validate meaning."""

from __future__ import annotations

from rest_framework import serializers

from .domain import enums
from .domain.catalogue import Category
from .domain.enums import choices
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
    category = serializers.ChoiceField(choices=[c.value for c in Category])
    channel = serializers.ChoiceField(choices=choices(enums.Channel))
    enabled = serializers.BooleanField()


class PreferencesWriteSerializer(serializers.Serializer):
    preferences = PreferenceItemSerializer(many=True, allow_empty=False, max_length=60)


class PermissionStateSerializer(serializers.Serializer):
    state = serializers.ChoiceField(choices=choices(enums.PermissionState))
    source = serializers.ChoiceField(choices=choices(enums.PermissionSource))


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
    }
