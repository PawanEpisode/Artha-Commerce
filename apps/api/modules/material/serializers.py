"""
Serializers for F-12 Institute Study Material (MAT).
"""

from __future__ import annotations

from rest_framework import serializers

from .models import Edition, EditionItem, Item, Progress, Provider, Report, UserProvider, Work


class ProviderSerializer(serializers.ModelSerializer):
    class Meta:
        model = Provider
        fields = [
            "id",
            "slug",
            "name",
            "normalised_name",
            "kind",
            "website_url",
            "status",
        ]


class ProviderCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=120)
    kind = serializers.ChoiceField(choices=Provider.Kind.choices, default=Provider.Kind.COACHING)
    slug = serializers.CharField(max_length=64, required=False, allow_blank=True)
    website_url = serializers.URLField(required=False, allow_blank=True)
    is_custom = serializers.BooleanField(default=False)


class FollowedProviderSerializer(serializers.ModelSerializer):
    provider_slug = serializers.CharField(source="provider.slug", read_only=True)
    provider_name = serializers.CharField(source="provider.name", read_only=True)

    class Meta:
        model = UserProvider
        fields = [
            "id",
            "provider_id",
            "provider_slug",
            "provider_name",
            "relation",
            "course_title",
            "batch_label",
            "purchased_on",
            "valid_until",
            "subject_keys",
        ]


class FollowedProviderUpdateSerializer(serializers.Serializer):
    provider_ids = serializers.ListField(child=serializers.UUIDField(), default=list)
    custom_names = serializers.ListField(child=serializers.CharField(max_length=120), default=list)


class CourseBoughtCreateSerializer(serializers.Serializer):
    provider_id = serializers.UUIDField()
    course_title = serializers.CharField(max_length=120)
    batch_label = serializers.CharField(max_length=60, default="", required=False)
    purchased_on = serializers.DateField(required=False, allow_null=True)
    valid_until = serializers.DateField(required=False, allow_null=True)
    subject_keys = serializers.ListField(child=serializers.CharField(), default=list)


class ProgressUpdateSerializer(serializers.Serializer):
    state = serializers.ChoiceField(choices=Progress.State.choices)
    edition_id = serializers.UUIDField()
    note = serializers.CharField(max_length=2000, default="", required=False, allow_blank=True)
    client_ts = serializers.DateTimeField(required=False)
    self_declared = serializers.BooleanField(default=False)


class ProgressBatchItemSerializer(serializers.Serializer):
    item_id = serializers.UUIDField()
    edition_id = serializers.UUIDField()
    state = serializers.ChoiceField(choices=Progress.State.choices)
    note = serializers.CharField(max_length=2000, default="", required=False, allow_blank=True)
    client_ts = serializers.DateTimeField(required=False)
    self_declared = serializers.BooleanField(default=False)


class ProgressBatchSerializer(serializers.Serializer):
    items = serializers.ListField(child=ProgressBatchItemSerializer(), max_length=100)


class UserEditionUpdateSerializer(serializers.Serializer):
    edition_id = serializers.UUIDField(allow_null=True)


class ReportCreateSerializer(serializers.Serializer):
    edition_id = serializers.UUIDField()
    kind = serializers.ChoiceField(choices=Report.Kind.choices)
    message = serializers.CharField(max_length=500, default="", required=False, allow_blank=True)


class WorkCreateSerializer(serializers.Serializer):
    provider_id = serializers.UUIDField()
    work_key = serializers.CharField(max_length=100)
    title = serializers.CharField(max_length=200)
    kind = serializers.ChoiceField(choices=Work.Kind.choices, default=Work.Kind.MODULE)
    base_work_id = serializers.UUIDField(required=False, allow_null=True)
    course_id = serializers.UUIDField()
    level_id = serializers.UUIDField()
    subject_key = serializers.CharField(max_length=64)
    subject_id = serializers.UUIDField(required=False, allow_null=True)


class PrivateWorkCreateSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=200)
    course_id = serializers.UUIDField()
    level_id = serializers.UUIDField()
    subject_key = serializers.CharField(max_length=64)
    subject_id = serializers.UUIDField(required=False, allow_null=True)
    provider_id = serializers.UUIDField(required=False, allow_null=True)


class DraftEditionCreateSerializer(serializers.Serializer):
    label = serializers.CharField(max_length=120)
    edition_date = serializers.DateField(required=False, allow_null=True)
    reprint_date = serializers.DateField(required=False, allow_null=True)
    applies_from_term = serializers.CharField(max_length=16)
    applies_to_term = serializers.CharField(max_length=16, required=False, allow_null=True, allow_blank=True)
    applicability_note = serializers.CharField(default="", required=False, allow_blank=True)
    source_url = serializers.URLField(required=False, allow_blank=True, allow_null=True)
    source_page_url = serializers.URLField(required=False, allow_blank=True, allow_null=True)
    page_offset = serializers.IntegerField(default=0)


class IndexImportSerializer(serializers.Serializer):
    items_data = serializers.ListField(child=serializers.DictField())
    units_data = serializers.ListField(child=serializers.DictField(), required=False, default=list)


class MatchDecisionSerializer(serializers.Serializer):
    decision = serializers.ChoiceField(choices=["same", "renamed", "new", "removed"])
    target_item_id = serializers.UUIDField(required=False, allow_null=True)
