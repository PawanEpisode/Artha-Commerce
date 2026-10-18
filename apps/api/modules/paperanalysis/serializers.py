"""
Serializers for F-11 Paper Analysis and Recommendations REST API.
"""

from __future__ import annotations

from decimal import Decimal

from rest_framework import serializers

from .domain.types import AllocationIn
from .models import (
    Allocation,
    ChoiceGroup,
    Paper,
    PaperQuestion,
    Plan,
    PlanItem,
    Settings,
)

# --- Editorial Serializers ---

class ChoiceGroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChoiceGroup
        fields = ["id", "label", "pick_n", "of_m", "note"]


class AllocationSerializer(serializers.ModelSerializer):
    chapter_name = serializers.CharField(source="chapter.name", read_only=True)

    class Meta:
        model = Allocation
        fields = [
            "id",
            "chapter_id",
            "chapter_key",
            "chapter_name",
            "topic_id",
            "marks",
            "share",
            "status",
            "origin",
            "basis",
            "confidence",
            "rationale",
            "model",
            "prompt_version",
            "suggested_at",
            "decided_by",
            "decided_at",
        ]


class PaperQuestionSerializer(serializers.ModelSerializer):
    allocations = AllocationSerializer(many=True, read_only=True)
    choice_group = ChoiceGroupSerializer(read_only=True)

    class Meta:
        model = PaperQuestion
        fields = [
            "id",
            "label",
            "position",
            "question_id",
            "question_version_id",
            "marks",
            "effective_marks",
            "choice_group",
            "format",
            "nature",
            "section_label",
            "source_ref",
            "tag_hint",
            "text_available",
            "alloc_state",
            "confirmed_by",
            "confirmed_at",
            "qa_state",
            "rev",
            "allocations",
        ]


class PaperListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Paper
        fields = [
            "id",
            "subject_id",
            "subject_key",
            "scheme_id",
            "term_code",
            "paper_kind",
            "series",
            "title",
            "status",
            "total_marks",
            "confirmed_marks",
            "marks_attemptable",
            "question_count",
            "rev",
            "is_limited",
            "created_at",
            "updated_at",
        ]


class PaperDetailSerializer(serializers.ModelSerializer):
    questions = PaperQuestionSerializer(many=True, read_only=True)
    choice_groups = ChoiceGroupSerializer(many=True, read_only=True)

    class Meta:
        model = Paper
        fields = [
            "id",
            "subject_id",
            "subject_key",
            "scheme_id",
            "term_code",
            "paper_kind",
            "series",
            "title",
            "status",
            "total_marks",
            "confirmed_marks",
            "marks_attemptable",
            "marks_optional_offered",
            "question_count",
            "rev",
            "is_limited",
            "source_url",
            "duration_minutes",
            "entry_mode",
            "exception_note",
            "questions",
            "choice_groups",
            "created_at",
            "updated_at",
        ]


class PaperCreateSerializer(serializers.Serializer):
    subject_id = serializers.UUIDField()
    term_code = serializers.CharField(max_length=16)
    paper_kind = serializers.ChoiceField(choices=Paper.PaperKind.choices, default=Paper.PaperKind.EXAM)
    series = serializers.CharField(max_length=32, required=False, default="")
    total_marks = serializers.DecimalField(max_digits=5, decimal_places=1, default=Decimal("100.0"))
    duration_minutes = serializers.IntegerField(required=False, default=180)
    source_url = serializers.URLField(required=False, allow_blank=True, default="")


class PaperPublishSerializer(serializers.Serializer):
    rev = serializers.IntegerField()
    exception_note = serializers.CharField(required=False, allow_blank=True, default=None)


class PaperUnpublishSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=255)


class AllocationInSerializer(serializers.Serializer):
    chapter_id = serializers.UUIDField()
    marks = serializers.DecimalField(max_digits=5, decimal_places=2)
    topic_id = serializers.UUIDField(required=False, allow_null=True, default=None)
    rationale = serializers.CharField(max_length=200, required=False, allow_blank=True, default="")

    def to_domain(self) -> AllocationIn:
        return AllocationIn(
            chapter_id=self.validated_data["chapter_id"],
            marks=self.validated_data["marks"],
            topic_id=self.validated_data.get("topic_id"),
            rationale=self.validated_data.get("rationale", ""),
        )


class SetAllocationsSerializer(serializers.Serializer):
    rev = serializers.IntegerField()
    allocations = AllocationInSerializer(many=True)


class ConfirmQuestionSerializer(serializers.Serializer):
    rev = serializers.IntegerField()


class QaDecisionSerializer(serializers.Serializer):
    qa_state = serializers.ChoiceField(choices=["agreed", "disputed"])
    note = serializers.CharField(required=False, allow_blank=True, default="")


class SkeletonImportSerializer(serializers.Serializer):
    csv_content = serializers.CharField()
    dry_run = serializers.BooleanField(default=False)


class SuggestSerializer(serializers.Serializer):
    question_ids = serializers.ListField(child=serializers.UUIDField(), required=False, default=list)


# --- Student Serializers ---

class SettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = Settings
        fields = [
            "window",
            "include_practice",
            "include_older",
            "show_reasons_default",
            "hide_tiers",
            "default_hours_per_day",
        ]


class PlanPreviewRequestSerializer(serializers.Serializer):
    days = serializers.IntegerField(min_value=1, max_value=90)
    hours_per_day = serializers.FloatField(min_value=0.5, max_value=14.0)
    subject_keys = serializers.ListField(child=serializers.CharField(), required=False, default=list)
    balance_subjects = serializers.BooleanField(default=False)


class PlanAdoptSerializer(serializers.Serializer):
    client_id = serializers.UUIDField()
    days = serializers.IntegerField(min_value=1, max_value=90)
    hours_per_day = serializers.FloatField(min_value=0.5, max_value=14.0)
    subject_keys = serializers.ListField(child=serializers.CharField(), required=False, default=list)
    balance_subjects = serializers.BooleanField(default=False)
    start_date = serializers.DateField(required=False, allow_null=True, default=None)


class PlanReplanSerializer(serializers.Serializer):
    days_remaining = serializers.IntegerField(min_value=1, max_value=90)
    hours_per_day = serializers.FloatField(min_value=0.5, max_value=14.0)


class PlanItemUpdateSerializer(serializers.Serializer):
    state = serializers.ChoiceField(choices=PlanItem.State.choices)
    planned_date = serializers.DateField(required=False, allow_null=True, default=None)


class PlanItemSerializer(serializers.ModelSerializer):
    chapter_name = serializers.CharField(source="chapter.name", read_only=True)

    class Meta:
        model = PlanItem
        fields = [
            "id",
            "chapter_id",
            "chapter_key",
            "chapter_name",
            "subject_key",
            "planned_date",
            "position",
            "minutes",
            "mode",
            "expected_gain",
            "mph",
            "state",
            "done_at",
            "moved_from",
        ]


class PlanSerializer(serializers.ModelSerializer):
    items = PlanItemSerializer(many=True, read_only=True)

    class Meta:
        model = Plan
        fields = [
            "id",
            "client_id",
            "status",
            "days",
            "hours_per_day",
            "tz",
            "start_date",
            "end_date",
            "subject_keys",
            "balance_subjects",
            "summary",
            "items",
            "created_at",
        ]


class FlagCreateSerializer(serializers.Serializer):
    target_type = serializers.CharField(max_length=32)
    target_id = serializers.UUIDField()
    note = serializers.CharField(max_length=500)
