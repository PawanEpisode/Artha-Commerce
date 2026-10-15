"""
Serializers for the Practice Engine API.
"""

from __future__ import annotations

from rest_framework import serializers

from .models import AttemptAnswer, Session


class CreateSessionSerializer(serializers.Serializer):
    origin = serializers.CharField(required=False, default="questionbank")
    mode = serializers.ChoiceField(
        choices=[c[0] for c in Session.Mode.choices],
        default=Session.Mode.UNTIMED,
    )
    title = serializers.CharField(required=False, allow_blank=True, max_length=200, default="")
    picker = serializers.CharField(required=False, default="filter")
    picker_params = serializers.DictField(required=False, default=dict)
    feedback_policy = serializers.CharField(required=False, allow_null=True, default=None)
    config = serializers.DictField(required=False, default=dict)
    client_id = serializers.UUIDField(required=False, allow_null=True, default=None)


class CreateSessionFromItemsSerializer(serializers.Serializer):
    origin = serializers.CharField(required=False, default="questionbank")
    mode = serializers.ChoiceField(
        choices=[c[0] for c in Session.Mode.choices],
        default=Session.Mode.UNTIMED,
    )
    title = serializers.CharField(required=False, allow_blank=True, max_length=200, default="")
    items = serializers.ListField(child=serializers.DictField(), min_length=1)
    config = serializers.DictField(required=False, default=dict)
    client_id = serializers.UUIDField(required=False, allow_null=True, default=None)


class SaveAnswerSerializer(serializers.Serializer):
    answer_json = serializers.JSONField(required=False, default=dict)
    client_ts = serializers.CharField(required=False, allow_blank=True, default="")
    time_spent_ms = serializers.IntegerField(required=False, default=0, min_value=0)
    confidence = serializers.IntegerField(required=False, allow_null=True, default=None)
    flagged = serializers.BooleanField(required=False, default=False)
    notes_md = serializers.CharField(required=False, allow_blank=True, default="")


class CheckAnswerSerializer(serializers.Serializer):
    answer_json = serializers.JSONField(required=False, default=dict)


class RetakeSessionSerializer(serializers.Serializer):
    scope = serializers.ChoiceField(choices=["all", "wrong", "unattempted", "flagged"], default="all")


class MistakeReasonSerializer(serializers.Serializer):
    mistake_reason = serializers.ChoiceField(
        choices=[c[0] for c in AttemptAnswer.MistakeReason.choices],
    )


class QuestionStateUpdateSerializer(serializers.Serializer):
    bookmarked = serializers.BooleanField(required=False, allow_null=True)
    notes = serializers.CharField(required=False, allow_blank=True)
