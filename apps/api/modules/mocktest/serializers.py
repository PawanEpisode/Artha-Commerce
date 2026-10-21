"""
DRF Serializers for F-08 Mock Tests.
"""

from __future__ import annotations

import uuid
from rest_framework import serializers


class StartAttemptSerializer(serializers.Serializer):
    paper_id = serializers.UUIDField()
    version_id = serializers.UUIDField(required=False, allow_null=True)
    run_mode = serializers.ChoiceField(choices=["exam", "relaxed"], default="exam")
    section_scope = serializers.CharField(required=False, allow_null=True, max_length=16)
    client_id = serializers.UUIDField(required=False, allow_null=True)
    tz = serializers.CharField(default="Asia/Kolkata", max_length=64)


class AcquireLeaseSerializer(serializers.Serializer):
    tab_id = serializers.CharField(max_length=64)
    label = serializers.CharField(max_length=120, default="Browser")
    takeover = serializers.BooleanField(default=False)


class HeartbeatSerializer(serializers.Serializer):
    epoch = serializers.IntegerField(min_value=1)
    position = serializers.IntegerField(required=False, allow_null=True)
    section = serializers.CharField(required=False, allow_null=True, max_length=16)
    events = serializers.ListField(child=serializers.DictField(), required=False, default=list)


class AnswerItemSerializer(serializers.Serializer):
    position = serializers.IntegerField(min_value=1)
    answer = serializers.JSONField(required=False, allow_null=True)
    flags = serializers.DictField(required=False, default=dict)
    client_ts = serializers.DateTimeField(required=False, allow_null=True)


class SaveAnswersBulkSerializer(serializers.Serializer):
    epoch = serializers.IntegerField(min_value=1)
    items = serializers.ListField(child=AnswerItemSerializer(), max_length=100)


class SaveAnswerSingleSerializer(serializers.Serializer):
    epoch = serializers.IntegerField(min_value=1)
    answer = serializers.JSONField(required=False, allow_null=True)
    flags = serializers.DictField(required=False, default=dict)
    client_ts = serializers.DateTimeField(required=False, allow_null=True)


class CloseSectionSerializer(serializers.Serializer):
    epoch = serializers.IntegerField(min_value=1)


class KeyStringParseSerializer(serializers.Serializer):
    text = serializers.CharField()


class BuilderPreviewSerializer(serializers.Serializer):
    marks = serializers.DecimalField(max_digits=7, decimal_places=2, default=100.0)
    duration_seconds = serializers.IntegerField(default=10800)
    chapter_ids = serializers.ListField(child=serializers.CharField(), default=list)
    seed = serializers.CharField(default="42")
    difficulty = serializers.CharField(default="mixed")


class BuilderGenerateSerializer(serializers.Serializer):
    course_id = serializers.UUIDField()
    level_id = serializers.UUIDField()
    scheme_id = serializers.UUIDField()
    subject_id = serializers.UUIDField(required=False, allow_null=True)
    subject_key = serializers.CharField(required=False, default="")
    title = serializers.CharField(required=False, allow_blank=True)
    marks = serializers.DecimalField(max_digits=7, decimal_places=2, default=100.0)
    duration_seconds = serializers.IntegerField(default=10800)
    chapter_ids = serializers.ListField(child=serializers.CharField(), default=list)
    seed = serializers.CharField(default="42")
    start = serializers.BooleanField(default=False)
    run_mode = serializers.ChoiceField(choices=["exam", "relaxed"], default="relaxed")


class SettingsPatchSerializer(serializers.Serializer):
    time_extension_pct = serializers.ChoiceField(choices=[0, 10, 25, 50, 100], required=False)
    default_run_mode = serializers.ChoiceField(choices=["exam", "relaxed"], required=False)
    focus_reminders = serializers.BooleanField(required=False)
    keyboard_shortcuts = serializers.BooleanField(required=False)
    percentile_optin = serializers.BooleanField(required=False, allow_null=True)
