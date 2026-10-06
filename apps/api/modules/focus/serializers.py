"""Input validation for the focus API. Output shapes come from `selectors`."""

from __future__ import annotations

from rest_framework import serializers

from modules.tracking.domain.durations import ACTIVITY_TYPES
from modules.tracking.serializers import SessionEditSerializer, SessionListQuerySerializer  # noqa: F401

from .domain import timing

ACTIVITY_CHOICES = list(ACTIVITY_TYPES)
PRESET_CHOICES = list(timing.PRESET_KEYS)


class _Optional(serializers.Serializer):
    def changes(self) -> dict:
        return dict(self.validated_data)


class SettingsSerializer(_Optional):
    preset = serializers.ChoiceField(choices=PRESET_CHOICES, required=False)
    focus_minutes = serializers.IntegerField(required=False)
    short_break_minutes = serializers.IntegerField(required=False)
    long_break_minutes = serializers.IntegerField(required=False)
    rounds_before_long = serializers.IntegerField(required=False)
    auto_start_breaks = serializers.BooleanField(required=False)
    auto_start_focus = serializers.BooleanField(required=False)
    overtime_enabled = serializers.BooleanField(required=False)
    sound_enabled = serializers.BooleanField(required=False)
    volume = serializers.IntegerField(required=False, min_value=0, max_value=100)
    notifications_enabled = serializers.BooleanField(required=False)
    keep_awake = serializers.BooleanField(required=False)
    keep_awake_in_breaks = serializers.BooleanField(required=False)
    intro_seen = serializers.BooleanField(required=False)


class TimerQuerySerializer(serializers.Serializer):
    alive = serializers.BooleanField(required=False, default=False)


class StartSerializer(serializers.Serializer):
    client_id = serializers.UUIDField()
    phase = serializers.ChoiceField(choices=list(timing.PHASES), required=False, default="focus")
    preset = serializers.ChoiceField(choices=PRESET_CHOICES, required=False)
    focus_minutes = serializers.IntegerField(required=False)
    short_break_minutes = serializers.IntegerField(required=False)
    long_break_minutes = serializers.IntegerField(required=False)
    rounds_before_long = serializers.IntegerField(required=False)
    subject_id = serializers.UUIDField(required=False, allow_null=True)
    chapter_id = serializers.UUIDField(required=False, allow_null=True)
    activity_type = serializers.ChoiceField(choices=ACTIVITY_CHOICES, required=False)
    at = serializers.DateTimeField(required=False, allow_null=True)

    def custom(self) -> dict:
        return {k: self.validated_data[k] for k in timing.PRESETS["classic"] if k in self.validated_data}


class ActionSerializer(serializers.Serializer):
    version = serializers.IntegerField(required=False, min_value=1)
    at = serializers.DateTimeField(required=False, allow_null=True)


class EndSerializer(serializers.Serializer):
    client_id = serializers.UUIDField(required=False)
    version = serializers.IntegerField(required=False, min_value=1)
    save = serializers.BooleanField(required=False, default=True)
    reason = serializers.ChoiceField(choices=list(timing.REASONS), required=False, allow_blank=True, default="")


class ClaimSerializer(serializers.Serializer):
    count = serializers.BooleanField()
    version = serializers.IntegerField(required=False, min_value=1)


class ContextSerializer(_Optional):
    version = serializers.IntegerField(min_value=1)
    subject_id = serializers.UUIDField(required=False, allow_null=True)
    chapter_id = serializers.UUIDField(required=False, allow_null=True)
    activity_type = serializers.ChoiceField(choices=ACTIVITY_CHOICES, required=False)
