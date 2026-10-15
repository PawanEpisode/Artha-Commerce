"""
Serializers for PYQ endpoints (F-09 ERD 3.2).
"""

from __future__ import annotations

from rest_framework import serializers


class StartPaperPracticeSerializer(serializers.Serializer):
    mode = serializers.ChoiceField(choices=["untimed", "timed"], default="untimed")
    client_id = serializers.UUIDField(required=False, allow_null=True)


class StartChapterPracticeSerializer(serializers.Serializer):
    count = serializers.IntegerField(default=10, min_value=1, max_value=50)
    client_id = serializers.UUIDField(required=False, allow_null=True)


class ImportPaperSerializer(serializers.Serializer):
    payload = serializers.JSONField()
    dry_run = serializers.BooleanField(default=False)


class WithdrawPaperSerializer(serializers.Serializer):
    reason = serializers.ChoiceField(choices=["takedown", "licence_ended", "editor", "replaced", "error"])
    replaced_by = serializers.UUIDField(required=False, allow_null=True)
