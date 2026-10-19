"""
REST Framework serializers for Progression and Level Transition (F-18).
"""

from __future__ import annotations

from rest_framework import serializers

from .models import ArticleshipProfile, LevelTransition, PaperResult


class PaperResultInputSerializer(serializers.Serializer):
    subject_key = serializers.CharField(max_length=80)
    status = serializers.ChoiceField(
        choices=PaperResult.PaperStatus.choices,
        default=PaperResult.PaperStatus.PENDING,
    )
    marks = serializers.IntegerField(
        min_value=0,
        max_value=100,
        required=False,
        allow_null=True,
    )
    is_carry_forward = serializers.BooleanField(default=False)
    is_permanent = serializers.BooleanField(default=False)


class ArticleshipInputSerializer(serializers.Serializer):
    is_active = serializers.BooleanField(default=False)
    firm_name = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")
    registration_number = serializers.CharField(max_length=64, required=False, allow_blank=True, default="")
    training_start_date = serializers.DateField(required=False, allow_null=True)
    expected_completion_date = serializers.DateField(required=False, allow_null=True)
    study_mode = serializers.ChoiceField(
        choices=ArticleshipProfile.StudyMode.choices,
        default=ArticleshipProfile.StudyMode.ACTIVE_STUDY,
    )
    weekday_minutes = serializers.IntegerField(min_value=0, max_value=1440, default=120)
    weekend_minutes = serializers.IntegerField(min_value=0, max_value=1440, default=360)
    exam_leave_start_date = serializers.DateField(required=False, allow_null=True)
    target_groups = serializers.ListField(
        child=serializers.CharField(max_length=64),
        required=False,
        default=list,
    )


class TransitionRequestSerializer(serializers.Serializer):
    transition_type = serializers.ChoiceField(choices=LevelTransition.TransitionType.choices)
    trigger = serializers.ChoiceField(
        choices=LevelTransition.Trigger.choices,
        default=LevelTransition.Trigger.USER_INITIATED,
    )
    target_course_code = serializers.CharField(max_length=16, required=False, allow_null=True, allow_blank=True)
    target_level_code = serializers.CharField(max_length=32, required=False, allow_null=True, allow_blank=True)
    target_scheme_id = serializers.UUIDField(required=False, allow_null=True)
    target_term_id = serializers.UUIDField(required=False, allow_null=True)
    cleared_group_keys = serializers.ListField(
        child=serializers.CharField(max_length=64),
        required=False,
        default=list,
    )
    paper_results = serializers.ListField(
        child=PaperResultInputSerializer(),
        required=False,
        default=list,
    )
    articleship = ArticleshipInputSerializer(required=False, allow_null=True)
    metadata = serializers.DictField(required=False, default=dict)


class RollbackRequestSerializer(serializers.Serializer):
    transition_id = serializers.UUIDField(required=True)
