"""
DRF serializers for student interactions, mutation requests, and editor operations.
"""

from __future__ import annotations

from rest_framework import serializers


class ReviewCardSerializer(serializers.Serializer):
    reviewed = serializers.BooleanField(required=True)
    client_id = serializers.UUIDField(required=False, allow_null=True)
    client_ts = serializers.DateTimeField(required=False, allow_null=True)


class SaveCardSerializer(serializers.Serializer):
    saved = serializers.BooleanField(required=True)
    client_id = serializers.UUIDField(required=False, allow_null=True)
    client_ts = serializers.DateTimeField(required=False, allow_null=True)


class BulkReviewSerializer(serializers.Serializer):
    public_ids = serializers.ListField(
        child=serializers.CharField(max_length=32),
        allow_empty=False,
        required=True,
    )
    reviewed = serializers.BooleanField(required=True)
    client_id = serializers.UUIDField(required=False, allow_null=True)


class ReportCardSerializer(serializers.Serializer):
    kind = serializers.ChoiceField(
        choices=[
            ("wrong_change", "Wrong Change"),
            ("wrong_mapping", "Wrong Mapping"),
            ("wrong_applicability", "Wrong Applicability"),
            ("missing_change", "Missing Change"),
            ("broken_link", "Broken Link"),
            ("other", "Other"),
        ],
        required=True,
    )
    message = serializers.CharField(max_length=1000, required=True)
