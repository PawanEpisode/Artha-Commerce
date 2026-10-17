"""
Data models for Performance Analytics (F-10 ERD section 2).
Provides read models, facts, user state, readiness profiles, goals, reports, and shares.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from django.db import models
from django.utils import timezone


class SessionRun(models.Model):
    """
    Lock, idempotency marker, and bookkeeping for processed practice sessions.
    """
    class State(models.TextChoices):
        OK = "ok", "OK"
        REMOVED = "removed", "Removed"
        FAILED = "failed", "Failed"

    session_id = models.UUIDField(primary_key=True)
    user_id = models.UUIDField(db_index=True)
    origin_module = models.CharField(max_length=64)
    mode = models.CharField(max_length=32)
    completion = models.CharField(max_length=32)
    session_created_at = models.DateTimeField()
    local_date = models.DateField(db_index=True)
    tz = models.CharField(max_length=64, default="Asia/Kolkata")
    content_hash = models.CharField(max_length=64, null=True, blank=True)
    fact_rows = models.SmallIntegerField(default=0)
    state = models.CharField(max_length=16, choices=State.choices, default=State.OK)
    attempts = models.SmallIntegerField(default=0)
    last_error = models.CharField(max_length=300, null=True, blank=True)
    first_refreshed_at = models.DateTimeField(null=True, blank=True)
    refreshed_at = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "analytics_sessionrun"
        indexes = [
            models.Index(fields=["user_id", "-refreshed_at"], name="an_srun_usr_ref_idx"),
            models.Index(fields=["user_id", "local_date"], name="an_srun_usr_date_idx"),
            models.Index(fields=["state", "refreshed_at"], name="an_srun_stat_ref_idx"),
        ]

    def __str__(self) -> str:
        return f"SessionRun({self.session_id}, user={self.user_id}, state={self.state})"


class ChapterFact(models.Model):
    """
    Chapter-grain performance facts per session.
    Values, not deltas.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    session_id = models.UUIDField(db_index=True)
    chapter_id = models.UUIDField(db_index=True)
    kind = models.CharField(max_length=32)
    difficulty = models.SmallIntegerField(default=0)
    source_kind = models.CharField(max_length=32, default="platform")
    is_repeat = models.BooleanField(default=False)
    local_date = models.DateField(db_index=True)
    user_id = models.UUIDField(db_index=True)
    subject_key = models.CharField(max_length=80)
    chapter_key = models.CharField(max_length=100, blank=True, default="")
    mode = models.CharField(max_length=32)

    answered = models.IntegerField(default=0)
    correct = models.IntegerField(default=0)
    incorrect = models.IntegerField(default=0)
    partial = models.IntegerField(default=0)
    skipped = models.IntegerField(default=0)
    credit_sum = models.DecimalField(max_digits=9, decimal_places=3, default=Decimal("0.000"))
    est_answered = models.IntegerField(default=0)
    est_credit_sum = models.DecimalField(max_digits=9, decimal_places=3, default=Decimal("0.000"))
    pending = models.IntegerField(default=0)

    time_n = models.IntegerField(default=0)
    time_ms_sum = models.BigIntegerField(default=0)
    sugg_n = models.IntegerField(default=0)
    sugg_ms_sum = models.BigIntegerField(default=0)
    nosugg_marks_sum = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal("0.00"))
    marks_awarded_sum = models.DecimalField(max_digits=9, decimal_places=2, default=Decimal("0.00"))
    marks_max_sum = models.DecimalField(max_digits=9, decimal_places=2, default=Decimal("0.00"))
    refreshed_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "analytics_chapterfact"
        constraints = [
            models.UniqueConstraint(
                fields=["session_id", "chapter_id", "kind", "difficulty", "source_kind", "is_repeat", "local_date"],
                name="uq_analytics_chapterfact_key",
            )
        ]
        indexes = [
            models.Index(fields=["user_id", "local_date"], name="an_cfact_usr_date_idx"),
            models.Index(fields=["user_id", "chapter_id", "local_date"], name="an_cfact_usr_ch_idx"),
            models.Index(fields=["user_id", "subject_key", "local_date"], name="an_cfact_usr_sub_idx"),
        ]

    def __str__(self) -> str:
        return f"ChapterFact(session={self.session_id}, ch={self.chapter_id}, ans={self.answered})"


class TopicFact(models.Model):
    """
    Topic-grain performance facts per session for weak topics identification.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    session_id = models.UUIDField(db_index=True)
    topic_id = models.UUIDField(db_index=True)
    is_repeat = models.BooleanField(default=False)
    local_date = models.DateField(db_index=True)
    user_id = models.UUIDField(db_index=True)
    chapter_id = models.UUIDField(db_index=True)
    subject_key = models.CharField(max_length=80)
    mode = models.CharField(max_length=32)

    answered = models.IntegerField(default=0)
    correct = models.IntegerField(default=0)
    incorrect = models.IntegerField(default=0)
    partial = models.IntegerField(default=0)
    skipped = models.IntegerField(default=0)
    credit_sum = models.DecimalField(max_digits=9, decimal_places=3, default=Decimal("0.000"))
    est_answered = models.IntegerField(default=0)
    est_credit_sum = models.DecimalField(max_digits=9, decimal_places=3, default=Decimal("0.000"))
    refreshed_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "analytics_topicfact"
        constraints = [
            models.UniqueConstraint(
                fields=["session_id", "topic_id", "is_repeat", "local_date"],
                name="uq_analytics_topicfact_key",
            )
        ]
        indexes = [
            models.Index(fields=["user_id", "local_date"], name="an_tfact_usr_date_idx"),
            models.Index(fields=["user_id", "topic_id", "local_date"], name="an_tfact_usr_top_idx"),
        ]

    def __str__(self) -> str:
        return f"TopicFact(session={self.session_id}, topic={self.topic_id}, ans={self.answered})"


class MistakeTag(models.Model):
    """
    Mistake categorization per wrong/partial answer.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    session_id = models.UUIDField(db_index=True)
    position = models.SmallIntegerField()
    user_id = models.UUIDField(db_index=True)
    chapter_id = models.UUIDField(db_index=True)
    subject_key = models.CharField(max_length=80)
    topic_id = models.UUIDField(null=True, blank=True)
    reason = models.CharField(max_length=32)
    local_date = models.DateField(db_index=True)
    tagged_at = models.DateTimeField(null=True, blank=True)
    refreshed_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "analytics_mistaketag"
        constraints = [
            models.UniqueConstraint(fields=["session_id", "position"], name="uq_analytics_mistake_pos")
        ]
        indexes = [
            models.Index(fields=["user_id", "local_date"], name="an_mtag_usr_date_idx"),
            models.Index(fields=["user_id", "chapter_id"], name="an_mtag_usr_ch_idx"),
        ]

    def __str__(self) -> str:
        return f"MistakeTag(session={self.session_id}, pos={self.position}, reason={self.reason})"


class UserState(models.Model):
    """
    Student-level metadata, cache version counter for ETag generation, and backfill watermark.
    """
    user_id = models.UUIDField(primary_key=True)
    facts_version = models.BigIntegerField(default=0)
    last_fact_at = models.DateTimeField(null=True, blank=True)
    last_session_at = models.DateTimeField(null=True, blank=True)
    reconciled_until = models.DateTimeField(null=True, blank=True)
    backfill_status = models.CharField(max_length=16, default="none")
    backfill_cursor = models.TextField(null=True, blank=True)
    backfilled_at = models.DateTimeField(null=True, blank=True)
    data_deleted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "analytics_userstate"

    def __str__(self) -> str:
        return f"UserState({self.user_id}, v={self.facts_version})"


class ReadinessProfile(models.Model):
    """
    Configurable readiness formula parameters per course / level.
    """
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        ACTIVE = "active", "Active"
        RETIRED = "retired", "Retired"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    course = models.ForeignKey("syllabus.Course", on_delete=models.RESTRICT, related_name="+")
    level = models.ForeignKey("syllabus.Level", null=True, blank=True, on_delete=models.RESTRICT, related_name="+")
    version = models.IntegerField(default=1)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.DRAFT)
    effective_from = models.DateField()
    effective_to = models.DateField(null=True, blank=True)

    w_accuracy = models.DecimalField(max_digits=4, decimal_places=3, default=Decimal("0.400"))
    w_breadth = models.DecimalField(max_digits=4, decimal_places=3, default=Decimal("0.150"))
    w_coverage = models.DecimalField(max_digits=4, decimal_places=3, default=Decimal("0.200"))
    w_retention = models.DecimalField(max_digits=4, decimal_places=3, default=Decimal("0.150"))
    w_speed = models.DecimalField(max_digits=4, decimal_places=3, default=Decimal("0.100"))

    half_life_days = models.SmallIntegerField(default=45)
    lookback_factor = models.SmallIntegerField(default=4)
    mode_weight_exam = models.DecimalField(max_digits=3, decimal_places=2, default=Decimal("1.25"))
    repeat_weight = models.DecimalField(max_digits=3, decimal_places=2, default=Decimal("0.50"))
    source_note = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "analytics_readinessprofile"
        constraints = [
            models.UniqueConstraint(fields=["course", "level", "version"], name="uq_analytics_profile_version")
        ]

    def __str__(self) -> str:
        return f"ReadinessProfile({self.course_id}, v={self.version}, {self.status})"


class ReadinessSnapshot(models.Model):
    """
    Historical point-in-time readiness snapshots.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    user_id = models.UUIDField(db_index=True)
    scope = models.CharField(max_length=16)  # 'overall', 'subject', 'group'
    scope_key = models.CharField(max_length=80, blank=True, default="")
    snapshot_date = models.DateField(db_index=True)
    score = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True)
    half_width = models.DecimalField(max_digits=3, decimal_places=1, null=True, blank=True)
    confidence = models.CharField(max_length=16, null=True, blank=True)
    state = models.CharField(max_length=16)
    profile = models.ForeignKey(ReadinessProfile, on_delete=models.RESTRICT, related_name="+")
    formula_version = models.IntegerField(default=1)
    components = models.JSONField(default=list)
    inputs = models.JSONField(default=dict)
    computed_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "analytics_readinesssnapshot"
        constraints = [
            models.UniqueConstraint(
                fields=["user_id", "scope", "scope_key", "snapshot_date"],
                name="uq_analytics_readiness_snapshot",
            )
        ]
        indexes = [
            models.Index(fields=["user_id", "scope", "scope_key", "-snapshot_date"], name="an_rsnap_usr_sc_idx"),
        ]

    def __str__(self) -> str:
        return f"ReadinessSnapshot(user={self.user_id}, scope={self.scope}:{self.scope_key}, date={self.snapshot_date}, score={self.score})"


class Goal(models.Model):
    """
    Student study goals for question volume and accuracy.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    user_id = models.UUIDField(db_index=True)
    metric = models.CharField(max_length=32)  # 'questions', 'accuracy'
    period = models.CharField(max_length=16)  # 'daily', 'weekly', 'none'
    subject_key = models.CharField(max_length=80, null=True, blank=True)
    target = models.DecimalField(max_digits=6, decimal_places=2)
    effective_from = models.DateField()
    effective_to = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "analytics_goal"
        indexes = [
            models.Index(fields=["user_id", "metric", "-effective_from"], name="an_goal_usr_met_idx"),
        ]

    def __str__(self) -> str:
        return f"Goal(user={self.user_id}, metric={self.metric}, target={self.target})"


class Settings(models.Model):
    """
    Student analytics preferences.
    """
    user_id = models.UUIDField(primary_key=True)
    target_accuracy = models.DecimalField(max_digits=3, decimal_places=2, null=True, blank=True)
    include_estimated = models.BooleanField(default=False)
    default_range = models.CharField(max_length=16, default="30d")
    version = models.IntegerField(default=1)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "analytics_settings"

    def __str__(self) -> str:
        return f"AnalyticsSettings(user={self.user_id}, target={self.target_accuracy})"


class Report(models.Model):
    """
    R2 Progress Reports (PDF and frozen data).
    """
    class Status(models.TextChoices):
        QUEUED = "queued", "Queued"
        BUILDING = "building", "Building"
        READY = "ready", "Ready"
        FAILED = "failed", "Failed"
        EXPIRED = "expired", "Expired"
        DELETED = "deleted", "Deleted"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    user_id = models.UUIDField(db_index=True)
    client_id = models.UUIDField()
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.QUEUED)
    period_kind = models.CharField(max_length=16)  # '30d', '90d', 'all', 'custom'
    from_date = models.DateField()
    to_date = models.DateField()
    subject_keys = models.JSONField(default=list)
    include_name = models.BooleanField(default=True)
    include_mistakes = models.BooleanField(default=False)
    include_time = models.BooleanField(default=True)
    display_name = models.CharField(max_length=120, blank=True, default="")
    report_version = models.SmallIntegerField(default=1)
    data = models.JSONField(null=True, blank=True)
    data_as_of = models.DateTimeField(null=True, blank=True)
    attachment_id = models.UUIDField(null=True, blank=True)
    error_code = models.CharField(max_length=32, null=True, blank=True)
    requested_at = models.DateTimeField(default=timezone.now)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    data_expires_at = models.DateTimeField(null=True, blank=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "analytics_report"
        constraints = [
            models.UniqueConstraint(fields=["user_id", "client_id"], name="uq_analytics_report_client")
        ]
        indexes = [
            models.Index(fields=["user_id", "-requested_at"], name="an_rep_usr_req_idx"),
            models.Index(fields=["status", "requested_at"], name="an_rep_stat_req_idx"),
        ]

    def __str__(self) -> str:
        return f"Report({self.id}, user={self.user_id}, status={self.status})"


class Share(models.Model):
    """
    R2 Public Share Links for frozen reports.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    user_id = models.UUIDField(db_index=True)
    report = models.ForeignKey(Report, on_delete=models.CASCADE, related_name="shares")
    token_hash = models.CharField(max_length=64, unique=True)
    scopes = models.JSONField(default=list)
    consent_version = models.CharField(max_length=32, default="v1")
    consented_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField()
    revoked_at = models.DateTimeField(null=True, blank=True)
    view_count = models.IntegerField(default=0)
    first_viewed_at = models.DateTimeField(null=True, blank=True)
    last_viewed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "analytics_share"
        indexes = [
            models.Index(fields=["user_id", "-created_at"], name="an_share_usr_cre_idx"),
        ]

    def __str__(self) -> str:
        return f"Share({self.id}, report={self.report_id})"
