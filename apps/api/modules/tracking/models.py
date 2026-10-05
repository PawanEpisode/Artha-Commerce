"""
Tables for study time. `StudySession` is the one table for every kind of study time (F-01.1 Pomodoro rounds, F-01.2
stopwatch, manual and later auto-captured time). The rest is the live stopwatch, settings, goals, derived roll-ups and
the short edit trail. `user_id` columns hold the Supabase user id by value (no cross-schema foreign key).
"""

import uuid

from django.db import models
from django.db.models import Q
from django.db.models.functions import Coalesce

from core.models import TimeStampedModel, UUIDModel

NIL_UUID = uuid.UUID(int=0)


class Source(models.TextChoices):
    POMODORO = "pomodoro", "Pomodoro"
    STOPWATCH = "stopwatch", "Stopwatch"
    MANUAL = "manual", "Manual"
    AUTO = "auto", "Auto"


class ActivityType(models.TextChoices):
    READING = "reading", "Reading"
    PRACTICE = "practice", "Practice"
    REVISION = "revision", "Revision"
    NOTES = "notes", "Notes"
    MOCK_TEST = "mock_test", "Mock test"
    OTHER = "other", "Other"


def _in(field: str, choices) -> Q:
    return Q(**{f"{field}__in": [value for value, _ in choices.choices]})


class StudySession(UUIDModel):
    """One block of study time. Includes every F-01.1 column so the Pomodoro build adds no migration here."""

    class Status(models.TextChoices):
        COMPLETED = "completed", "Completed"
        PARTIAL = "partial", "Partial"

    user_id = models.UUIDField()
    client_id = models.UUIDField(null=True, blank=True)
    source = models.CharField(max_length=10, choices=Source.choices, default=Source.POMODORO)
    activity_type = models.CharField(max_length=10, choices=ActivityType.choices, default=ActivityType.OTHER)
    subject = models.ForeignKey(
        "syllabus.Subject", null=True, blank=True, on_delete=models.SET_NULL, related_name="study_sessions"
    )
    chapter = models.ForeignKey(
        "syllabus.Chapter", null=True, blank=True, on_delete=models.SET_NULL, related_name="study_sessions"
    )
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.COMPLETED)
    started_at = models.DateTimeField()
    ended_at = models.DateTimeField()
    planned_seconds = models.IntegerField(null=True, blank=True)
    focus_seconds = models.IntegerField()
    paused_total_seconds = models.IntegerField(default=0)
    pause_count = models.SmallIntegerField(default=0)
    round_number = models.SmallIntegerField(null=True, blank=True)
    cycle_id = models.UUIDField(null=True, blank=True)
    interruption_reason = models.CharField(max_length=12, blank=True, default="")
    auto_closed = models.BooleanField(default=False)
    presence_verified = models.BooleanField(default=True)
    study_date = models.DateField()
    tz = models.CharField(max_length=64)
    note = models.CharField(max_length=500, blank=True, default="")
    # F-01.2 additions
    is_edited = models.BooleanField(default=False)
    edit_count = models.SmallIntegerField(default=0)
    original_started_at = models.DateTimeField(null=True, blank=True)
    original_ended_at = models.DateTimeField(null=True, blank=True)
    overlaps_other = models.BooleanField(default=False)
    split_from = models.ForeignKey("self", null=True, blank=True, on_delete=models.SET_NULL, related_name="split_parts")
    merged_count = models.SmallIntegerField(default=1)
    idle_trimmed = models.BooleanField(default=False)

    class Meta:
        db_table = "tracking_studysession"
        constraints = [
            models.UniqueConstraint(
                fields=["user_id", "client_id"],
                condition=Q(client_id__isnull=False),
                name="tracking_studysession_client_unique",
            ),
            # Live-captured rows (Pomodoro, stopwatch) are capped at 12 h; a manual or auto entry may be up to 24 h.
            models.CheckConstraint(
                condition=Q(focus_seconds__gte=60)
                & Q(focus_seconds__lte=86400)
                & (Q(source__in=["manual", "auto"]) | Q(focus_seconds__lte=43200)),
                name="tracking_studysession_focus_range",
            ),
            models.CheckConstraint(
                condition=Q(ended_at__gte=models.F("started_at")), name="tracking_studysession_order"
            ),
            models.CheckConstraint(
                condition=Q(status__in=("completed", "partial")), name="tracking_studysession_status_valid"
            ),
            models.CheckConstraint(condition=_in("source", Source), name="tracking_studysession_source_valid"),
            models.CheckConstraint(
                condition=_in("activity_type", ActivityType), name="tracking_studysession_activity_valid"
            ),
            models.CheckConstraint(
                condition=Q(interruption_reason="") | Q(status="partial"), name="tracking_studysession_reason_partial"
            ),
            # Only Pomodoro rows can be partial; stopwatch, manual and auto rows are always completed.
            models.CheckConstraint(
                condition=Q(status="completed") | Q(source="pomodoro"), name="tracking_studysession_partial_pomodoro"
            ),
            models.CheckConstraint(
                condition=Q(source="pomodoro") | (Q(round_number__isnull=True) & Q(cycle_id__isnull=True)),
                name="tracking_studysession_round_pomodoro",
            ),
        ]
        indexes = [
            models.Index(fields=["user_id", "-study_date"], name="tracking_session_day_idx"),
            models.Index(fields=["user_id", "-started_at"], name="tracking_session_started_idx"),
            models.Index(fields=["user_id", "subject", "-started_at"], name="tracking_session_subject_idx"),
            models.Index(fields=["user_id", "chapter"], name="tracking_session_chapter_idx"),
            models.Index(fields=["user_id", "source", "-started_at"], name="tracking_session_source_idx"),
            models.Index(fields=["user_id", "study_date", "started_at"], name="tracking_session_overlap_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.source} {self.started_at:%Y-%m-%d %H:%M} ({self.focus_seconds}s)"


class ActiveStopwatch(TimeStampedModel):
    """The live stopwatch. One row per student (the primary key), present only while running or paused."""

    user_id = models.UUIDField(primary_key=True)
    started_at = models.DateTimeField()
    paused_at = models.DateTimeField(null=True, blank=True)
    paused_total_seconds = models.IntegerField(default=0)
    pause_count = models.SmallIntegerField(default=0)
    last_seen_at = models.DateTimeField()
    last_active_at = models.DateTimeField()
    idle_pending = models.BooleanField(default=False)
    idle_prompted_at = models.DateTimeField(null=True, blank=True)
    subject = models.ForeignKey("syllabus.Subject", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    chapter = models.ForeignKey("syllabus.Chapter", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    activity_type = models.CharField(max_length=10, choices=ActivityType.choices, default=ActivityType.OTHER)
    client_id = models.UUIDField()
    version = models.IntegerField(default=1)

    class Meta:
        db_table = "tracking_activestopwatch"
        constraints = [
            models.CheckConstraint(
                condition=_in("activity_type", ActivityType), name="tracking_stopwatch_activity_valid"
            ),
            models.CheckConstraint(condition=Q(paused_total_seconds__gte=0), name="tracking_stopwatch_pause_total"),
        ]


class TrackerSettings(TimeStampedModel):
    user_id = models.UUIDField(primary_key=True)
    idle_minutes = models.SmallIntegerField(default=10)
    week_start = models.SmallIntegerField(default=1)  # 1 = Monday, 0 = Sunday
    default_activity_type = models.CharField(max_length=10, choices=ActivityType.choices, default=ActivityType.READING)
    tz = models.CharField(max_length=64, default="Asia/Kolkata")

    class Meta:
        db_table = "tracking_trackersettings"
        constraints = [
            models.CheckConstraint(
                condition=Q(idle_minutes=0) | (Q(idle_minutes__gte=5) & Q(idle_minutes__lte=60)),
                name="tracking_settings_idle_range",
            ),
            models.CheckConstraint(condition=Q(week_start__in=[0, 1]), name="tracking_settings_week_start"),
            models.CheckConstraint(
                condition=_in("default_activity_type", ActivityType), name="tracking_settings_activity_valid"
            ),
        ]


class Goal(models.Model):
    """Effective-dated goal. Changing a goal closes the old row and opens a new one, so history is never rewritten."""

    class Period(models.TextChoices):
        DAILY = "daily", "Daily"
        WEEKLY = "weekly", "Weekly"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user_id = models.UUIDField()
    period = models.CharField(max_length=6, choices=Period.choices)
    subject = models.ForeignKey("syllabus.Subject", null=True, blank=True, on_delete=models.CASCADE, related_name="+")
    subject_key = models.CharField(max_length=80, blank=True, default="")
    target_minutes = models.IntegerField()
    effective_from = models.DateField()
    effective_to = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "tracking_goal"
        constraints = [
            models.CheckConstraint(condition=Q(period__in=("daily", "weekly")), name="tracking_goal_period_valid"),
            models.CheckConstraint(
                condition=(Q(period="daily") & Q(target_minutes__gte=15) & Q(target_minutes__lte=1440))
                | (Q(period="weekly") & Q(target_minutes__gte=30) & Q(target_minutes__lte=10080)),
                name="tracking_goal_target_range",
            ),
            models.CheckConstraint(
                condition=Q(effective_to__isnull=True) | Q(effective_to__gte=models.F("effective_from")),
                name="tracking_goal_dates_ordered",
            ),
            # At most one open goal per student, period and subject key ("" = the overall goal).
            models.UniqueConstraint(
                "user_id",
                "period",
                "subject_key",
                condition=Q(effective_to__isnull=True),
                name="tracking_goal_one_open",
            ),
        ]
        indexes = [models.Index(fields=["user_id", "period", "-effective_from"], name="tracking_goal_lookup_idx")]

    def __str__(self) -> str:
        return f"{self.period} goal {self.target_minutes} min from {self.effective_from}"


class DailyRollup(models.Model):
    """Derived: seconds per student, local day and tag combination. Rebuildable from the sessions, never the truth."""

    user_id = models.UUIDField()
    study_date = models.DateField()
    subject = models.ForeignKey("syllabus.Subject", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    chapter = models.ForeignKey("syllabus.Chapter", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    activity_type = models.CharField(max_length=10)
    source = models.CharField(max_length=10)
    verified = models.BooleanField(default=True)
    seconds = models.IntegerField(default=0)
    sessions = models.SmallIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "tracking_dailyrollup"
        constraints = [
            models.UniqueConstraint(
                "user_id",
                "study_date",
                Coalesce("subject", models.Value(NIL_UUID, output_field=models.UUIDField())),
                Coalesce("chapter", models.Value(NIL_UUID, output_field=models.UUIDField())),
                "activity_type",
                "source",
                "verified",
                name="tracking_dailyrollup_key",
            )
        ]
        indexes = [
            models.Index(fields=["user_id", "study_date"], name="tracking_rollup_day_idx"),
            models.Index(fields=["user_id", "subject", "study_date"], name="tracking_rollup_subject_idx"),
            models.Index(
                fields=["user_id", "chapter", "study_date"],
                condition=Q(chapter__isnull=False),
                name="tracking_rollup_chapter_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.study_date} {self.source} {self.seconds}s"


class HourBucket(models.Model):
    """Derived: seconds per local hour, for the best-hours chart. Approximate for sessions that had pauses."""

    user_id = models.UUIDField()
    study_date = models.DateField()
    hour = models.SmallIntegerField()
    seconds = models.IntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "tracking_hourbucket"
        constraints = [
            models.UniqueConstraint(fields=["user_id", "study_date", "hour"], name="tracking_hourbucket_key"),
            models.CheckConstraint(condition=Q(hour__gte=0) & Q(hour__lte=23), name="tracking_hourbucket_hour"),
        ]
        indexes = [models.Index(fields=["user_id", "study_date"], name="tracking_hour_day_idx")]

    def __str__(self) -> str:
        return f"{self.study_date} {self.hour:02d}h {self.seconds}s"


class SessionAudit(models.Model):
    """Short trail for undo (10 s) and support (30 days). Never holds note text."""

    class Action(models.TextChoices):
        DELETE = "delete", "Delete"
        MERGE = "merge", "Merge"
        SPLIT = "split", "Split"
        EDIT_TIMES = "edit_times", "Edit times"
        MANUAL_TRIM = "manual_trim", "Manual trim"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user_id = models.UUIDField()
    action = models.CharField(max_length=12, choices=Action.choices)
    snapshot = models.JSONField(default=dict)
    session_count = models.SmallIntegerField(default=1)
    undo_until = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "tracking_sessionaudit"
        constraints = [
            models.CheckConstraint(
                condition=Q(action__in=("delete", "merge", "split", "edit_times", "manual_trim")),
                name="tracking_audit_action_valid",
            )
        ]
        indexes = [models.Index(fields=["user_id", "-created_at"], name="tracking_audit_user_idx")]

    def __str__(self) -> str:
        return f"{self.action} x{self.session_count}"
