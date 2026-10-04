"""
Private per-student syllabus coverage (F-02). Every row is scoped by `user_id` (the Supabase user UUID, by value).

`CoverageEvent` is the append-only ledger and the source of truth. `ChapterProgress`, `TopicProgress` and `Rollup`
are derived and can be rebuilt from it (`python manage.py rebuild_coverage`).
See docs/product/erd/F-02-syllabus-structure-and-coverage.md section 3.
"""

from django.db import models
from django.db.models import Q
from django.utils import timezone

from core.models import TimeStampedModel, UUIDModel
from modules.syllabus.models import Chapter, ExamTerm, Level, Scheme, Topic

DEFAULT_REVISION_DAYS = [3, 7, 21, 45]


class Enrollment(UUIDModel):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        ARCHIVED = "archived", "Archived"

    user_id = models.UUIDField(db_index=True)
    scheme = models.ForeignKey(Scheme, on_delete=models.PROTECT, related_name="enrollments")
    # Denormalised from scheme.level so the one-active-enrolment-per-level rule is a plain partial unique index.
    level = models.ForeignKey(Level, on_delete=models.PROTECT, related_name="enrollments")
    target_term = models.ForeignKey(ExamTerm, null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    exam_date = models.DateField(null=True, blank=True)
    daily_hours = models.DecimalField(max_digits=3, decimal_places=1, null=True, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ACTIVE)
    carried_from = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.SET_NULL, related_name="carried_to"
    )

    class Meta:
        db_table = "coverage_enrollment"
        constraints = [
            models.UniqueConstraint(
                fields=["user_id", "level"], condition=Q(status="active"), name="coverage_one_active_per_level"
            ),
            models.CheckConstraint(condition=Q(status__in=["active", "archived"]), name="coverage_enrollment_status"),
            models.CheckConstraint(
                condition=Q(daily_hours__isnull=True) | Q(daily_hours__gt=0, daily_hours__lte=24),
                name="coverage_enrollment_hours",
            ),
        ]


class CoverageSettings(TimeStampedModel):
    """One row per student, created on first read with defaults. Weights must total 100."""

    user_id = models.UUIDField(primary_key=True)
    w_read = models.SmallIntegerField(default=40)
    w_practice = models.SmallIntegerField(default=30)
    w_revise = models.SmallIntegerField(default=20)
    w_mock = models.SmallIntegerField(default=10)
    # Stored as a JSON array so the same model runs on Postgres (jsonb) and in SQLite tests. 1 to 8 gaps, 1..365 days.
    revision_days = models.JSONField(default=list)
    weighted_default = models.BooleanField(default=False)

    class Meta:
        db_table = "coverage_settings"
        constraints = [
            models.CheckConstraint(
                condition=Q(w_read__gte=0, w_read__lte=100)
                & Q(w_practice__gte=0, w_practice__lte=100)
                & Q(w_revise__gte=0, w_revise__lte=100)
                & Q(w_mock__gte=0, w_mock__lte=100),
                name="coverage_settings_weight_range",
            ),
            models.CheckConstraint(
                condition=Q(w_read=100 - models.F("w_practice") - models.F("w_revise") - models.F("w_mock")),
                name="coverage_settings_weights_total_100",
            ),
        ]


class TopicProgress(models.Model):
    user_id = models.UUIDField()
    topic = models.ForeignKey(Topic, on_delete=models.PROTECT, related_name="progress")
    pk = models.CompositePrimaryKey("user_id", "topic_id")
    enrollment = models.ForeignKey(Enrollment, on_delete=models.CASCADE, related_name="topic_progress")
    is_done = models.BooleanField(default=False)
    done_at = models.DateTimeField(null=True, blank=True)
    source = models.CharField(max_length=12, default="manual")
    # Compared against the client's event time for last-write-wins between devices.
    updated_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "coverage_topicprogress"
        indexes = [models.Index(fields=["enrollment", "is_done"], name="coverage_topic_done_idx")]

    def __str__(self) -> str:
        return f"{self.user_id} {self.topic_id}"


class ChapterProgress(UUIDModel):
    class Status(models.TextChoices):
        NOT_STARTED = "not_started", "Not started"
        READING = "reading", "Reading"
        PRACTISED = "practised", "Practised"
        REVISED_ONCE = "revised_once", "Revised once"
        REVISED_TWICE_PLUS = "revised_twice_plus", "Revised twice or more"
        EXAM_READY = "exam_ready", "Exam ready"

    class Confidence(models.TextChoices):
        RED = "red", "Red"
        AMBER = "amber", "Amber"
        GREEN = "green", "Green"

    user_id = models.UUIDField()
    enrollment = models.ForeignKey(Enrollment, on_delete=models.CASCADE, related_name="chapter_progress")
    chapter = models.ForeignKey(Chapter, on_delete=models.PROTECT, related_name="progress")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.NOT_STARTED)
    confidence = models.CharField(max_length=6, choices=Confidence.choices, blank=True, default="")
    is_excluded = models.BooleanField(default=False)
    # A chapter without topics uses one implicit topic: the chapter itself is tickable (ERD amendment, section 3.4).
    implicit_topic_done = models.BooleanField(default=False)
    read_pct = models.SmallIntegerField(default=0)
    practice_pct = models.SmallIntegerField(default=0)
    revise_pct = models.SmallIntegerField(default=0)
    mock_pct = models.SmallIntegerField(default=0)
    coverage_pct = models.SmallIntegerField(default=0)
    practice_count = models.SmallIntegerField(default=0)
    mock_count = models.SmallIntegerField(default=0)
    revision_count = models.SmallIntegerField(default=0)
    total_study_seconds = models.IntegerField(default=0)
    first_started_at = models.DateTimeField(null=True, blank=True)
    last_studied_at = models.DateTimeField(null=True, blank=True)
    last_revised_at = models.DateTimeField(null=True, blank=True)
    next_revision_due = models.DateField(null=True, blank=True)

    class Meta:
        db_table = "coverage_chapterprogress"
        constraints = [
            models.UniqueConstraint(fields=["user_id", "chapter"], name="coverage_chapterprogress_unique"),
            models.CheckConstraint(
                condition=Q(
                    status__in=[
                        "not_started",
                        "reading",
                        "practised",
                        "revised_once",
                        "revised_twice_plus",
                        "exam_ready",
                    ]
                ),
                name="coverage_chapterprogress_status",
            ),
            models.CheckConstraint(
                condition=Q(confidence__in=["", "red", "amber", "green"]), name="coverage_chapterprogress_confidence"
            ),
            models.CheckConstraint(condition=Q(coverage_pct__gte=0, coverage_pct__lte=100), name="coverage_pct_range"),
        ]
        indexes = [
            models.Index(fields=["enrollment", "chapter"], name="coverage_cp_enrol_chapter_idx"),
            models.Index(
                fields=["enrollment", "next_revision_due"],
                condition=Q(next_revision_due__isnull=False, is_excluded=False),
                name="coverage_cp_due_idx",
            ),
            models.Index(fields=["user_id", "-last_studied_at"], name="coverage_cp_recent_idx"),
        ]


class CoverageEvent(UUIDModel):
    """Append-only ledger. Never updated or deleted, except by the account-deletion service."""

    class Type(models.TextChoices):
        TOPIC_DONE = "topic_done", "Topic done"
        TOPIC_UNDONE = "topic_undone", "Topic undone"
        PRACTICE_DONE = "practice_done", "Practice done"
        MOCK_DONE = "mock_done", "Mock done"
        REVISION_DONE = "revision_done", "Revision done"
        STUDY_TIME = "study_time", "Study time"
        CONFIDENCE_SET = "confidence_set", "Confidence set"
        EXCLUDED = "excluded", "Excluded"
        INCLUDED = "included", "Included"
        NOTE_ADDED = "note_added", "Note added"

    class Source(models.TextChoices):
        MANUAL = "manual", "Manual"
        CATCHUP = "catchup", "Catch-up"
        TRACKING = "tracking", "Tracking"
        QUESTION_BANK = "question_bank", "Question bank"
        MOCK = "mock", "Mock"
        NOTES = "notes", "Notes"
        CARRYOVER = "carryover", "Carry-over"
        SYSTEM = "system", "System"

    user_id = models.UUIDField()
    enrollment = models.ForeignKey(Enrollment, on_delete=models.CASCADE, related_name="events")
    chapter = models.ForeignKey(Chapter, on_delete=models.PROTECT, related_name="+")
    topic = models.ForeignKey(Topic, null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    type = models.CharField(max_length=16, choices=Type.choices)
    value = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    payload = models.JSONField(default=dict)
    source = models.CharField(max_length=14, choices=Source.choices, default=Source.MANUAL)
    source_ref = models.CharField(max_length=64, blank=True)
    client_id = models.UUIDField(null=True, blank=True)
    occurred_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "coverage_event"
        constraints = [
            models.UniqueConstraint(
                fields=["user_id", "client_id"],
                condition=Q(client_id__isnull=False),
                name="coverage_event_client_id_unique",
            ),
        ]
        indexes = [
            models.Index(fields=["enrollment", "chapter", "occurred_at"], name="coverage_event_chapter_idx"),
            models.Index(fields=["user_id", "-occurred_at"], name="coverage_event_user_idx"),
        ]


class Rollup(models.Model):
    """Derived cache of subject, group and level percentages for one enrolment."""

    class NodeType(models.TextChoices):
        SUBJECT = "subject", "Subject"
        GROUP = "group", "Group"
        LEVEL = "level", "Level"

    enrollment = models.ForeignKey(Enrollment, on_delete=models.CASCADE, related_name="rollups")
    node_type = models.CharField(max_length=8, choices=NodeType.choices)
    node_id = models.UUIDField()
    pk = models.CompositePrimaryKey("enrollment_id", "node_type", "node_id")
    pct_simple = models.SmallIntegerField(default=0)
    pct_weighted = models.SmallIntegerField(default=0)
    chapters_total = models.SmallIntegerField(default=0)
    chapters_done = models.SmallIntegerField(default=0)
    updated_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "coverage_rollup"

    def __str__(self) -> str:
        return f"{self.enrollment_id} {self.node_type} {self.node_id}"
