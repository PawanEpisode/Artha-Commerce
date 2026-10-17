"""
REST serializers for Performance Analytics (F-10).
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from django.utils import timezone
from rest_framework import serializers

from .models import Goal, Report, Settings, Share


class BuildFixSetSerializer(serializers.Serializer):
    scope_type = serializers.ChoiceField(choices=["topic", "chapter"], required=False)
    scope_id = serializers.UUIDField(required=False)
    topic_id = serializers.UUIDField(required=False)
    chapter_id = serializers.UUIDField(required=False)
    size = serializers.IntegerField(required=False, default=10, min_value=5, max_value=20)
    limit = serializers.IntegerField(required=False, min_value=5, max_value=20)
    client_id = serializers.UUIDField(required=False, default=uuid.uuid4)
    tz = serializers.CharField(required=False, default="Asia/Kolkata")

    def validate(self, attrs):
        if not attrs.get("scope_type") or not attrs.get("scope_id"):
            if attrs.get("topic_id"):
                attrs["scope_type"] = "topic"
                attrs["scope_id"] = attrs["topic_id"]
            elif attrs.get("chapter_id"):
                attrs["scope_type"] = "chapter"
                attrs["scope_id"] = attrs["chapter_id"]
            else:
                raise serializers.ValidationError(
                    "Either (scope_type and scope_id) or topic_id or chapter_id must be provided."
                )
        if "limit" in attrs and attrs.get("limit"):
            attrs["size"] = attrs["limit"]
        return attrs


class RefreshSerializer(serializers.Serializer):
    limit = serializers.IntegerField(default=10, min_value=1, max_value=100)


class GoalSerializer(serializers.ModelSerializer):
    target_kind = serializers.CharField(required=False)
    target_value = serializers.CharField(required=False)

    class Meta:
        model = Goal
        fields = (
            "id",
            "metric",
            "period",
            "subject_key",
            "target",
            "effective_from",
            "effective_to",
            "target_kind",
            "target_value",
        )
        read_only_fields = ("id",)
        extra_kwargs = {
            "metric": {"required": False},
            "period": {"required": False, "default": "daily"},
            "target": {"required": False},
            "effective_from": {"required": False},
        }

    def validate(self, attrs):
        if "target_kind" in attrs and not attrs.get("metric"):
            attrs["metric"] = attrs.pop("target_kind")
        if "target_value" in attrs and not attrs.get("target"):
            try:
                attrs["target"] = Decimal(str(attrs.pop("target_value")))
            except Exception:
                raise serializers.ValidationError({"target_value": "Invalid target value."})
        if not attrs.get("metric"):
            attrs["metric"] = "questions"
        if not attrs.get("period"):
            attrs["period"] = "daily"
        if "target" not in attrs:
            raise serializers.ValidationError({"target": "Target or target_value is required."})
        if not attrs.get("effective_from"):
            attrs["effective_from"] = timezone.localdate()
        return attrs

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["target_kind"] = instance.metric
        data["target_value"] = str(instance.target)
        return data


class SettingsSerializer(serializers.ModelSerializer):
    target_accuracy = serializers.CharField(required=False, allow_null=True)
    target_pace_ratio = serializers.CharField(required=False, allow_blank=True)
    decay_half_life_days = serializers.IntegerField(required=False)
    time_budget_minutes_per_day = serializers.IntegerField(required=False)

    class Meta:
        model = Settings
        fields = (
            "target_accuracy",
            "include_estimated",
            "default_range",
            "version",
            "target_pace_ratio",
            "decay_half_life_days",
            "time_budget_minutes_per_day",
        )
        read_only_fields = ("version",)

    def validate_target_accuracy(self, value):
        if value is not None and value != "":
            try:
                dec = Decimal(str(value).replace("%", "").strip())
                if dec > Decimal("1.0"):
                    dec = dec / Decimal("100.0")
                return round(dec, 2)
            except Exception:
                raise serializers.ValidationError("Enter a valid target accuracy (e.g. 0.85 or 85).")
        return None


class RequestReportSerializer(serializers.Serializer):
    period_kind = serializers.ChoiceField(choices=["7d", "30d", "90d", "all", "custom"], default="30d")
    from_date = serializers.DateField(required=False, allow_null=True)
    to_date = serializers.DateField(required=False, allow_null=True)
    subject_keys = serializers.ListField(child=serializers.CharField(), required=False, default=list)
    include_name = serializers.BooleanField(required=False, default=True)
    include_mistakes = serializers.BooleanField(required=False, default=False)
    include_time = serializers.BooleanField(required=False, default=True)
    client_id = serializers.UUIDField(required=False, default=uuid.uuid4)


class CreateShareSerializer(serializers.Serializer):
    report_id = serializers.UUIDField()
    scopes = serializers.ListField(child=serializers.CharField(), required=False, default=list)
    expires_in_days = serializers.IntegerField(required=False, default=30, min_value=1, max_value=90)
    consent_version = serializers.CharField(required=False, default="v1")
