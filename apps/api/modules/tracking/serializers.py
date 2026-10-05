"""Input validation and output shapes for the tracking API."""

from __future__ import annotations

from rest_framework import serializers

from .domain import durations
from .domain.reports import GROUPS

ACTIVITY_CHOICES = list(durations.ACTIVITY_TYPES)
SOURCE_CHOICES = list(durations.SOURCES)


class _Optional(serializers.Serializer):
    """Base for PATCH-like bodies: only the keys sent end up in `changes`."""

    def changes(self) -> dict:
        return dict(self.validated_data)


class StopwatchStartSerializer(serializers.Serializer):
    client_id = serializers.UUIDField()
    subject_id = serializers.UUIDField(required=False, allow_null=True)
    chapter_id = serializers.UUIDField(required=False, allow_null=True)
    activity_type = serializers.ChoiceField(choices=ACTIVITY_CHOICES, required=False)
    at = serializers.DateTimeField(required=False, allow_null=True)


class StopwatchActionSerializer(serializers.Serializer):
    version = serializers.IntegerField(required=False, min_value=1)
    at = serializers.DateTimeField(required=False, allow_null=True)


class StopwatchStopSerializer(serializers.Serializer):
    client_id = serializers.UUIDField(required=False)
    version = serializers.IntegerField(required=False, min_value=1)
    save = serializers.BooleanField(required=False, default=True)
    end_at = serializers.DateTimeField(required=False, allow_null=True)


class StopwatchContextSerializer(_Optional):
    version = serializers.IntegerField(min_value=1)
    subject_id = serializers.UUIDField(required=False, allow_null=True)
    chapter_id = serializers.UUIDField(required=False, allow_null=True)
    activity_type = serializers.ChoiceField(choices=ACTIVITY_CHOICES, required=False)


class StopwatchIdleSerializer(serializers.Serializer):
    answer = serializers.ChoiceField(choices=["prompted", "still_studying"])


class StopwatchQuerySerializer(serializers.Serializer):
    alive = serializers.BooleanField(required=False, default=False)
    active = serializers.BooleanField(required=False, default=False)


class ManualSessionSerializer(serializers.Serializer):
    client_id = serializers.UUIDField()
    started_at = serializers.DateTimeField()
    ended_at = serializers.DateTimeField(required=False)
    duration_seconds = serializers.IntegerField(
        required=False, min_value=durations.MIN_SESSION_SECONDS, max_value=durations.MAX_MANUAL_SPAN_SECONDS
    )
    subject_id = serializers.UUIDField(required=False, allow_null=True)
    chapter_id = serializers.UUIDField(required=False, allow_null=True)
    activity_type = serializers.ChoiceField(choices=ACTIVITY_CHOICES, required=False, default="other")
    note = serializers.CharField(required=False, allow_blank=True, max_length=durations.NOTE_MAX_CHARS, default="")
    on_overlap = serializers.ChoiceField(choices=["trim", "keep", "reject"], required=False, allow_null=True)
    confirm_old = serializers.BooleanField(required=False, default=False)

    def validate(self, attrs):
        if not attrs.get("ended_at") and not attrs.get("duration_seconds"):
            raise serializers.ValidationError({"ended_at": "Give an end time or a duration."})
        return attrs


class SessionEditSerializer(_Optional):
    subject_id = serializers.UUIDField(required=False, allow_null=True)
    chapter_id = serializers.UUIDField(required=False, allow_null=True)
    activity_type = serializers.ChoiceField(choices=ACTIVITY_CHOICES, required=False)
    note = serializers.CharField(required=False, allow_blank=True, max_length=durations.NOTE_MAX_CHARS)
    started_at = serializers.DateTimeField(required=False)
    ended_at = serializers.DateTimeField(required=False)
    confirm_old = serializers.BooleanField(required=False)


class UndoSerializer(serializers.Serializer):
    undo_token = serializers.UUIDField()
    # The note is not kept in the audit trail (privacy); the page resends it from its own copy for those 10 seconds.
    notes = serializers.DictField(
        child=serializers.CharField(allow_blank=True, max_length=durations.NOTE_MAX_CHARS), required=False
    )


class MergeSerializer(_Optional):
    session_ids = serializers.ListField(child=serializers.UUIDField(), min_length=2, max_length=20)
    subject_id = serializers.UUIDField(required=False, allow_null=True)
    chapter_id = serializers.UUIDField(required=False, allow_null=True)
    activity_type = serializers.ChoiceField(choices=ACTIVITY_CHOICES, required=False)


class AutoCaptureSerializer(serializers.Serializer):
    client_id = serializers.UUIDField()
    chapter_id = serializers.UUIDField()
    started_at = serializers.DateTimeField()
    seconds = serializers.IntegerField(min_value=1, max_value=durations.AUTO_MAX_CHUNK_SECONDS)


class SplitSerializer(serializers.Serializer):
    at = serializers.DateTimeField()


class GoalEntrySerializer(serializers.Serializer):
    period = serializers.ChoiceField(choices=["daily", "weekly"])
    subject_id = serializers.UUIDField(required=False, allow_null=True)
    target_minutes = serializers.IntegerField(min_value=1, max_value=100000)


class GoalsSerializer(serializers.Serializer):
    goals = GoalEntrySerializer(many=True, max_length=100)


class SettingsSerializer(_Optional):
    idle_minutes = serializers.IntegerField(required=False, min_value=0, max_value=durations.IDLE_MINUTES_MAX)
    week_start = serializers.IntegerField(required=False, min_value=0, max_value=1)
    default_activity_type = serializers.ChoiceField(choices=ACTIVITY_CHOICES, required=False)
    tz = serializers.CharField(required=False, max_length=64)
    auto_capture_enabled = serializers.BooleanField(required=False)


class _RangeBase(serializers.Serializer):
    """`from` and `to` are Python keywords, so the two fields are added by name."""

    def get_fields(self):
        fields = super().get_fields()
        fields["from"] = serializers.DateField(required=False)
        fields["to"] = serializers.DateField(required=False)
        return fields


class SessionListQuerySerializer(_RangeBase):
    subject_id = serializers.UUIDField(required=False)
    chapter_id = serializers.UUIDField(required=False)
    source = serializers.ChoiceField(choices=SOURCE_CHOICES, required=False)
    cursor = serializers.CharField(required=False, max_length=200)
    limit = serializers.IntegerField(required=False, min_value=1, max_value=100, default=50)
    include_notes = serializers.BooleanField(required=False, default=False)


class ReportQuerySerializer(_RangeBase):
    compare = serializers.BooleanField(required=False, default=False)
    group = serializers.ChoiceField(choices=list(GROUPS), required=False, default="day")
    by = serializers.CharField(required=False, default="total", max_length=16)
    parent_id = serializers.CharField(required=False, max_length=120)
    subject_id = serializers.UUIDField(required=False)
    verified_only = serializers.BooleanField(required=False, default=False)
    week_start = serializers.DateField(required=False)
    include_notes = serializers.BooleanField(required=False, default=False)


def session_dict(s, *, include_note: bool = True) -> dict:
    out = {
        "id": s.id,
        "client_id": s.client_id,
        "source": s.source,
        "activity_type": s.activity_type,
        "subject_id": s.subject_id,
        "subject_name": s.subject.name if s.subject_id else "",
        "chapter_id": s.chapter_id,
        "chapter_name": s.chapter.name if s.chapter_id else "",
        "status": s.status,
        "started_at": s.started_at,
        "ended_at": s.ended_at,
        "focus_seconds": s.focus_seconds,
        "paused_total_seconds": s.paused_total_seconds,
        "pause_count": s.pause_count,
        "study_date": s.study_date,
        "tz": s.tz,
        "is_edited": s.is_edited,
        "overlaps_other": s.overlaps_other,
        "merged_count": s.merged_count,
        "idle_trimmed": s.idle_trimmed,
        "presence_verified": s.presence_verified,
        "split_from_id": s.split_from_id,
    }
    if include_note:
        out["note"] = s.note
    return out


def settings_dict(s) -> dict:
    return {
        "idle_minutes": s.idle_minutes,
        "week_start": s.week_start,
        "default_activity_type": s.default_activity_type,
        "tz": s.tz,
        "auto_capture_enabled": s.auto_capture_enabled,
    }


def goal_dict(g) -> dict:
    return {
        "id": g.id,
        "period": g.period,
        "subject_id": g.subject_id,
        "subject_key": g.subject_key,
        "subject_name": g.subject.name if g.subject_id else "",
        "target_minutes": g.target_minutes,
        "effective_from": g.effective_from,
    }
