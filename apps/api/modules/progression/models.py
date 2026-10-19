"""
Database models for Level Transition, Student Progression, Articleship Mode, and Paper Exemptions (F-18).
"""

from __future__ import annotations

from django.db import models
from django.db.models import Q
from django.utils import timezone

from core.models import UUIDModel


class LevelTransition(UUIDModel):
    """
    Immutable ledger of discrete level graduations, group clearances, and syllabus transitions.
    """

    class TransitionType(models.TextChoices):
        FULL_LEVEL_PASS = "full_level_pass", "Full Level Pass"
        GROUP_CLEARANCE = "group_clearance", "Group Clearance"
        EXEMPTION_UPDATE = "exemption_update", "Exemption Update"
        SCHEME_MIGRATION = "scheme_migration", "Scheme Migration"
        REPEAT_ATTEMPT = "repeat_attempt", "Repeat Attempt"

    class Trigger(models.TextChoices):
        RESULT_PROMPT = "result_prompt", "Result Prompt"
        USER_INITIATED = "user_initiated", "User Initiated"
        ADMIN = "admin", "Admin"

    class Status(models.TextChoices):
        APPLIED = "applied", "Applied"
        REVERTED = "reverted", "Reverted"
        FAILED = "failed", "Failed"

    user_id = models.UUIDField(db_index=True)
    from_enrollment = models.ForeignKey(
        "coverage.Enrollment",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="transitions_from",
    )
    to_enrollment = models.ForeignKey(
        "coverage.Enrollment",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="transitions_to",
    )
    transition_type = models.CharField(max_length=32, choices=TransitionType.choices)
    trigger = models.CharField(max_length=32, choices=Trigger.choices, default=Trigger.USER_INITIATED)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.APPLIED)
    effective_date = models.DateField(default=timezone.now)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "progression_level_transition"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user_id", "-created_at"], name="prg_trans_user_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(
                    transition_type__in=[
                        "full_level_pass",
                        "group_clearance",
                        "exemption_update",
                        "scheme_migration",
                        "repeat_attempt",
                    ]
                ),
                name="prg_transition_type_valid",
            ),
            models.CheckConstraint(
                condition=Q(status__in=["applied", "reverted", "failed"]),
                name="prg_transition_status_valid",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.user_id} - {self.transition_type} ({self.status})"


class PaperResult(UUIDModel):
    """
    Paper-by-paper outcomes reported during a term result transition.
    """

    class PaperStatus(models.TextChoices):
        PASSED = "passed", "Passed"
        EXEMPTED = "exempted", "Exempted"
        PENDING = "pending", "Pending"
        FAILED = "failed", "Failed"

    transition = models.ForeignKey(
        LevelTransition,
        on_delete=models.CASCADE,
        related_name="paper_results",
    )
    user_id = models.UUIDField(db_index=True)
    subject_key = models.CharField(max_length=80)
    status = models.CharField(max_length=16, choices=PaperStatus.choices)
    marks_obtained = models.SmallIntegerField(null=True, blank=True)
    is_carry_forward = models.BooleanField(default=False)

    class Meta:
        db_table = "progression_paper_result"
        indexes = [
            models.Index(fields=["user_id", "subject_key"], name="prg_paper_res_user_idx"),
        ]
        constraints = [
            models.UniqueConstraint(fields=["transition", "subject_key"], name="prg_paper_res_uniq"),
            models.CheckConstraint(
                condition=Q(status__in=["passed", "exempted", "pending", "failed"]),
                name="prg_paper_res_status_valid",
            ),
            models.CheckConstraint(
                condition=Q(marks_obtained__isnull=True)
                | Q(marks_obtained__gte=0, marks_obtained__lte=100),
                name="prg_paper_res_marks_valid",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.user_id} - {self.subject_key}: {self.status} ({self.marks_obtained})"


class ArticleshipProfile(UUIDModel):
    """
    Stores practical training details and lifestyle study constraints (weekday vs weekend split).
    """

    class StudyMode(models.TextChoices):
        ACTIVE_STUDY = "active_study", "Active Study"
        WEEKEND_ONLY = "weekend_only", "Weekend Only"
        WORK_FOCUS_PAUSE = "work_focus_pause", "Work Focus Pause"
        EXAM_LEAVE_INTENSIVE = "exam_leave_intensive", "Exam Leave Intensive"

    user_id = models.UUIDField(unique=True, db_index=True)
    is_active = models.BooleanField(default=False)
    firm_name = models.CharField(max_length=255, blank=True, default="")
    registration_number = models.CharField(max_length=64, blank=True, default="")
    training_start_date = models.DateField(null=True, blank=True)
    expected_completion_date = models.DateField(null=True, blank=True)
    study_mode = models.CharField(
        max_length=32,
        choices=StudyMode.choices,
        default=StudyMode.ACTIVE_STUDY,
    )
    weekday_minutes = models.SmallIntegerField(default=120)
    weekend_minutes = models.SmallIntegerField(default=360)
    exam_leave_start_date = models.DateField(null=True, blank=True)
    target_groups = models.JSONField(default=list, blank=True)

    class Meta:
        db_table = "progression_articleship_profile"
        constraints = [
            models.CheckConstraint(
                condition=Q(
                    study_mode__in=[
                        "active_study",
                        "weekend_only",
                        "work_focus_pause",
                        "exam_leave_intensive",
                    ]
                ),
                name="prg_articleship_mode_valid",
            ),
            models.CheckConstraint(
                condition=Q(weekday_minutes__gte=0, weekday_minutes__lte=1440),
                name="prg_articleship_weekday_valid",
            ),
            models.CheckConstraint(
                condition=Q(weekend_minutes__gte=0, weekend_minutes__lte=1440),
                name="prg_articleship_weekend_valid",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.user_id} Articleship (active={self.is_active}, mode={self.study_mode})"


class ExemptionLedger(UUIDModel):
    """
    Tracks official exemptions granted under the Institute 60+ marks rule.
    """

    user_id = models.UUIDField(db_index=True)
    subject_key = models.CharField(max_length=80)
    marks_obtained = models.SmallIntegerField()
    granted_term_code = models.CharField(max_length=32)
    valid_until_term_code = models.CharField(max_length=32, blank=True, default="")
    is_permanent = models.BooleanField(default=False)
    is_exhausted = models.BooleanField(default=False)

    class Meta:
        db_table = "progression_exemption_ledger"
        indexes = [
            models.Index(fields=["user_id", "is_exhausted"], name="prg_exemption_user_idx"),
            models.Index(fields=["user_id", "subject_key"], name="prg_exemption_subject_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(marks_obtained__gte=60),
                name="prg_exemption_marks_gte_60",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.user_id} - {self.subject_key} ({self.marks_obtained} marks, exhausted={self.is_exhausted})"
