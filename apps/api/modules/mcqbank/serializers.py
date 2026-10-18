"""
Serializers for MCQ Bank endpoints.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from rest_framework import serializers

# Matches `McqBlueprintPickerSpec.count` (le=100): the most questions one quick session can hold.
MAX_QUICK_PRACTICE_COUNT = 100


class ExternalLogCreateSerializer(serializers.Serializer):
    set_id = serializers.UUIDField()
    score = serializers.DecimalField(max_digits=7, decimal_places=2, min_value=Decimal("0"))
    max_score = serializers.DecimalField(max_digits=7, decimal_places=2, min_value=Decimal("0.01"))
    taken_on = serializers.DateField()
    client_id = serializers.UUIDField(default=uuid.uuid4)

    def validate(self, attrs):
        if attrs["score"] > attrs["max_score"]:
            raise serializers.ValidationError({"score": "Score cannot exceed max_score."})
        return attrs


class SavePresetSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=60)
    kind = serializers.ChoiceField(choices=["builder", "blueprint", "pattern"], default="builder")
    mode = serializers.ChoiceField(
        choices=["untimed", "timed", "chapter_quiz", "revision", "custom_test"], default="untimed"
    )
    picker = serializers.CharField(max_length=32)
    spec = serializers.JSONField(default=dict)
    time_limit_seconds = serializers.IntegerField(required=False, allow_null=True, min_value=60, max_value=14400)
    scoring_profile = serializers.CharField(default="practice")
    pattern_id = serializers.UUIDField(required=False, allow_null=True)
    client_id = serializers.UUIDField(required=False, allow_null=True)


class StartQuickPracticeSerializer(serializers.Serializer):
    chapter_id = serializers.UUIDField(required=False, allow_null=True)
    subject_key = serializers.CharField(max_length=80, required=False)
    count = serializers.IntegerField(default=10, min_value=1, max_value=MAX_QUICK_PRACTICE_COUNT)
    mode = serializers.ChoiceField(choices=["untimed", "timed", "chapter_quiz", "revision"], default="chapter_quiz")
    # "instant" shows right and wrong after every answer; "at_end" holds the markings until submit.
    # Left out, the mode decides (chapter_quiz holds them until the end).
    feedback_policy = serializers.ChoiceField(choices=["instant", "at_end"], required=False)
    client_id = serializers.UUIDField(default=uuid.uuid4)


class WithdrawSetSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=32)


class AdaptiveStartSerializer(serializers.Serializer):
    scope_type = serializers.ChoiceField(choices=["chapter", "subject"])
    scope_id = serializers.UUIDField()
    subject_key = serializers.CharField(max_length=80)
    chapter_key = serializers.CharField(max_length=80, required=False, default="")
    client_id = serializers.UUIDField(default=uuid.uuid4)


class BlueprintPreviewSerializer(serializers.Serializer):
    spec = serializers.JSONField()
