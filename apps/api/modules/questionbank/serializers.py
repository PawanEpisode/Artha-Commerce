"""
Serializers for Question Bank API endpoints (F-06 ERD 3.2, 3.6).
"""

from __future__ import annotations

from rest_framework import serializers


class CreateDraftSerializer(serializers.Serializer):
    kind = serializers.CharField(max_length=32, default="mcq_single")
    stem_md = serializers.CharField(max_length=20_000)
    options = serializers.ListField(child=serializers.DictField(), required=False, default=list)
    numeric_key = serializers.DictField(required=False, allow_null=True)
    explanation_md = serializers.CharField(max_length=30_000, required=False, default="", allow_blank=True)
    explanation_source = serializers.CharField(max_length=200, required=False, default="", allow_blank=True)
    reference_labels = serializers.ListField(child=serializers.CharField(), required=False, default=list)
    marks = serializers.DecimalField(max_digits=5, decimal_places=1, default=1.0)
    negative_marks = serializers.DecimalField(max_digits=4, decimal_places=2, required=False, allow_null=True)
    multi_scoring = serializers.CharField(max_length=20, default="all_or_nothing")
    rubric = serializers.DictField(required=False, allow_null=True)
    children = serializers.ListField(child=serializers.DictField(), required=False, default=list)
    labels = serializers.DictField(required=False, default=dict)
    client_id = serializers.UUIDField(required=False, allow_null=True)


class SaveLiveSerializer(serializers.Serializer):
    visibility = serializers.ChoiceField(choices=["private", "link"])


class ReportErrorSerializer(serializers.Serializer):
    version_id = serializers.UUIDField()
    kind = serializers.CharField(max_length=32)
    message = serializers.CharField(max_length=1000, required=False, default="", allow_blank=True)
    proposed_option_ids = serializers.ListField(child=serializers.UUIDField(), required=False, default=list)


class DecideReviewSerializer(serializers.Serializer):
    decision = serializers.ChoiceField(choices=["approved", "changes_requested", "rejected"])
    code = serializers.CharField(max_length=32)
    note = serializers.CharField(required=False, default="", allow_blank=True)
    field_comments = serializers.ListField(child=serializers.DictField(), required=False, default=list)


class PublishVersionSerializer(serializers.Serializer):
    visibility = serializers.ChoiceField(choices=["public", "link", "private"], default="public")


class VerifySerializer(serializers.Serializer):
    version_id = serializers.UUIDField()
    level = serializers.CharField(max_length=32, default="editor")
    source_label = serializers.CharField(max_length=200)
    source_url = serializers.URLField(required=False, allow_blank=True, default="")


class MergeDuplicateSerializer(serializers.Serializer):
    loser_id = serializers.UUIDField()
    canonical_id = serializers.UUIDField()
