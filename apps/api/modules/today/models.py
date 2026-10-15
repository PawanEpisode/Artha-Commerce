"""
Tables for Today (F-13 R1 and, from migration 0002, the R2 planner; ERD section 2). Today stores decisions, not knowledge: a task
row is a snapshot of one offer made to one student on one day; the truth about the underlying work stays in the owning module. `user_id` holds the Supabase user id by
value (no cross-schema foreign key). `subject_id` and `chapter_id` are real foreign keys that become NULL if the syllabus row is
removed; the stable `subject_key` and `chapter_key` copies keep links working across a scheme switch.

Counters on `DayPlan` are recomputed from the tasks under the plan lock, never incremented (ERD 0.6).
"""

import uuid

from core.models import TimeStampedModel, UUIDModel
from django.db import models
from django.db.models import F, Q, TextField, Value
from django.db.models.functions import Cast, Greatest, Length
from django.db.models.lookups import LessThanOrEqual

from .domain import constants as c
from .planner import constants as pc


def _in(field: str, values) -> Q:
    return Q(**{f"{field}__in": list(values)})


def _choices(values):
    return [(v, v) for v in values]


def _json_size_ok(field: str, limit: int):
    """The JSON column, rendered as text, is at most `limit` characters (a cheap guard; services also check the byte size)."""
    return LessThanOrEqual(Length(Cast(field, output_field=TextField())), limit)


class DayPlan(UUIDModel):
    """One row per student per local date (unique), created by generation (`ready`) or by a first own task for a future day (`draft`)."""

    user_id = models.UUIDField()
    local_date = models.DateField()
    tz = models.CharField(max_length=64)
    status = models.CharField(max_length=6, choices=_choices(c.PLAN_STATUSES), default="ready")
    generation_no = models.SmallIntegerField(default=1)
    algorithm_version = models.SmallIntegerField(default=c.ALGORITHM_VERSION)
    phase = models.CharField(max_length=11, choices=_choices(c.PHASES), default="steady")
    exam_date = models.DateField(null=True, blank=True)
    days_to_exam = models.SmallIntegerField(null=True, blank=True)  # negative once the date has passed
    budget_minutes = models.SmallIntegerField(default=60)
    budget_source = models.CharField(max_length=8, choices=_choices(c.BUDGET_SOURCES), default="auto")
    planned_count = models.SmallIntegerField(default=0)
    done_count = models.SmallIntegerField(default=0)
    skipped_count = models.SmallIntegerField(default=0)
    open_count = models.SmallIntegerField(default=0)
    snoozed_count = models.SmallIntegerField(default=0)
    planned_minutes = models.SmallIntegerField(default=0)
    open_minutes = models.SmallIntegerField(default=0)
    partial = models.BooleanField(default=False)
    provider_status = models.JSONField(default=dict)
    selection_log = models.JSONField(default=dict)  # counts only, never titles
    context_hash = models.CharField(max_length=64, null=True, blank=True)  # noqa: DJ001 - NULL until a plan is generated (a draft has none)
    generated_at = models.DateTimeField(null=True, blank=True)
    first_opened_at = models.DateTimeField(null=True, blank=True)
    celebrated_at = models.DateTimeField(null=True, blank=True)  # the celebration shows once per day across devices
    closed_at = models.DateTimeField(null=True, blank=True)
    version = models.IntegerField(default=1)  # optimistic lock for regenerate, and the ETag

    class Meta:
        db_table = "today_dayplan"
        constraints = [
            models.UniqueConstraint(fields=["user_id", "local_date"], name="today_dayplan_user_date_uniq"),
            models.CheckConstraint(condition=_in("status", c.PLAN_STATUSES), name="today_dayplan_status_valid"),
            models.CheckConstraint(
                condition=Q(status="draft") | Q(generation_no__gte=1), name="today_dayplan_generation_valid"
            ),
            models.CheckConstraint(condition=_in("phase", c.PHASES), name="today_dayplan_phase_valid"),
            models.CheckConstraint(
                condition=Q(budget_minutes__gte=c.BUDGET_MIN, budget_minutes__lte=c.BUDGET_MAX),
                name="today_dayplan_budget_range",
            ),
            models.CheckConstraint(condition=_in("budget_source", c.BUDGET_SOURCES), name="today_dayplan_source_valid"),
            models.CheckConstraint(
                condition=_json_size_ok("selection_log", c.SELECTION_LOG_MAX_CHARS), name="today_dayplan_log_size"
            ),
        ]
        indexes = [
            models.Index(fields=["local_date"], name="today_plan_ready_idx", condition=Q(status="ready")),
            models.Index(fields=["local_date", "user_id"], name="today_plan_date_user_idx"),
        ]


class Task(UUIDModel):
    """One offer to one student on one day: a provider's task, the student's own, or (R2) a planner milestone."""

    user_id = models.UUIDField()
    plan = models.ForeignKey(DayPlan, on_delete=models.CASCADE, related_name="tasks")
    local_date = models.DateField()  # equals the plan's date; moves with an own task that is snoozed
    origin = models.CharField(max_length=8, choices=_choices(c.ORIGINS))
    provider = models.CharField(max_length=64, blank=True, default="")
    kind = models.CharField(max_length=40)  # a registered kind name; open for extension, so validated in code
    slot = models.CharField(max_length=10, choices=_choices(c.SLOTS))
    dedupe_key = models.CharField(max_length=c.DEDUPE_KEY_MAX)
    title = models.CharField(max_length=c.TITLE_MAX)  # plain text
    reason_code = models.CharField(max_length=40, default="custom")
    reason = models.CharField(max_length=c.REASON_MAX, blank=True, default="")
    link_path = models.CharField(max_length=200, blank=True, default="")
    link_search = models.JSONField(default=dict)
    est_minutes = models.SmallIntegerField()
    subject = models.ForeignKey("syllabus.Subject", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    chapter = models.ForeignKey("syllabus.Chapter", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    subject_key = models.CharField(max_length=64, blank=True, default="")
    chapter_key = models.CharField(max_length=64, blank=True, default="")
    target_value = models.SmallIntegerField(null=True, blank=True)  # for count tasks (5 MCQs, 12 cards)
    progress_value = models.SmallIntegerField(default=0)  # sum of evidence deltas, capped at the target
    position = models.SmallIntegerField(default=0)
    is_must_do = models.BooleanField(default=False)
    is_pinned = models.BooleanField(default=False)  # kept across regeneration
    counts_toward_day = models.BooleanField(default=True)  # false for bonus tasks (R2)
    state = models.CharField(max_length=9, choices=_choices(c.TASK_STATES), default="suggested")
    prev_state = models.CharField(max_length=9, null=True, blank=True)  # noqa: DJ001 - NULL until the first transition
    state_changed_at = models.DateTimeField(auto_now_add=True)
    completed_via = models.CharField(max_length=6, null=True, blank=True, choices=_choices(c.COMPLETED_VIA))  # noqa: DJ001 - NULL unless done
    completed_at = models.DateTimeField(null=True, blank=True)
    skip_reason = models.CharField(max_length=14, null=True, blank=True, choices=_choices(c.SKIP_REASONS))  # noqa: DJ001 - NULL unless skipped; "" is not a reason
    end_reason = models.CharField(max_length=16, null=True, blank=True, choices=_choices(c.END_REASONS))  # noqa: DJ001 - NULL unless expired; "" is not a reason
    snoozed_until = models.DateField(null=True, blank=True)
    snooze_count = models.SmallIntegerField(default=0)
    carry_count = models.SmallIntegerField(default=0)  # own tasks carried to a new day; at 3 the task is flagged stuck
    score = models.IntegerField(default=0)
    score_breakdown = models.JSONField(default=dict)  # "Why this?" without re-running anything
    payload = models.JSONField(default=dict)
    manual_action = models.JSONField(null=True, blank=True)  # {"key", "label", "default"}; the code is looked up by key
    client_id = models.UUIDField(null=True, blank=True)  # idempotency key of own-task creation and of swap replacements
    last_client_id = models.UUIDField(null=True, blank=True)  # idempotency key of the last transition
    swapped_from_id = models.UUIDField(null=True, blank=True)
    version = models.IntegerField(default=1)  # optimistic lock
    deleted_at = models.DateTimeField(null=True, blank=True)  # own tasks only (soft delete)

    class Meta:
        db_table = "today_task"
        constraints = [
            models.CheckConstraint(condition=_in("origin", c.ORIGINS), name="today_task_origin_valid"),
            models.CheckConstraint(condition=_in("slot", c.SLOTS), name="today_task_slot_valid"),
            models.CheckConstraint(condition=_in("state", c.TASK_STATES), name="today_task_state_valid"),
            models.CheckConstraint(
                condition=Q(origin="user") | (~Q(provider="") & ~Q(dedupe_key="")), name="today_task_provider_key"
            ),
            models.CheckConstraint(
                condition=Q(est_minutes__gte=c.OWN_EST_MIN, est_minutes__lte=c.OWN_EST_MAX), name="today_task_est_range"
            ),
            models.CheckConstraint(
                condition=Q(target_value__isnull=True) | Q(target_value__gte=1, target_value__lte=100),
                name="today_task_target_range",
            ),
            models.CheckConstraint(condition=Q(progress_value__gte=0), name="today_task_progress_nonneg"),
            models.CheckConstraint(
                condition=Q(link_path="") | Q(link_path__startswith="/app/"), name="today_task_link_internal"
            ),
            # done and completed_at go together; the other optional columns only make sense in their own state.
            models.CheckConstraint(
                condition=(Q(state="done") & Q(completed_at__isnull=False))
                | (~Q(state="done") & Q(completed_at__isnull=True)),
                name="today_task_done_stamp",
            ),
            models.CheckConstraint(
                condition=Q(completed_via__isnull=True) | Q(state="done"), name="today_task_via_only_done"
            ),
            models.CheckConstraint(
                condition=(Q(state="snoozed") & Q(snoozed_until__isnull=False))
                | (~Q(state="snoozed") & Q(snoozed_until__isnull=True)),
                name="today_task_snooze_date",
            ),
            models.CheckConstraint(
                condition=Q(skip_reason__isnull=True) | Q(state="skipped"), name="today_task_skip_reason_state"
            ),
            models.CheckConstraint(
                condition=Q(end_reason__isnull=True) | Q(state="expired"), name="today_task_end_reason_state"
            ),
            models.CheckConstraint(
                condition=Q(skip_reason__isnull=True) | _in("skip_reason", c.SKIP_REASONS),
                name="today_task_skip_reason_valid",
            ),
            models.CheckConstraint(
                condition=Q(end_reason__isnull=True) | _in("end_reason", c.END_REASONS),
                name="today_task_end_reason_valid",
            ),
            models.CheckConstraint(
                condition=Q(completed_via__isnull=True) | _in("completed_via", c.COMPLETED_VIA),
                name="today_task_via_valid",
            ),
            models.CheckConstraint(
                condition=_json_size_ok("payload", c.PAYLOAD_MAX_CHARS), name="today_task_payload_size"
            ),
            # One live row per unit of work per day, including skipped and done, so a done or skipped key is never re-suggested.
            models.UniqueConstraint(
                fields=["plan", "dedupe_key"],
                condition=~Q(state="expired") & Q(deleted_at__isnull=True),
                name="today_task_live_key_uniq",
            ),
            models.UniqueConstraint(
                fields=["user_id", "client_id"], condition=Q(client_id__isnull=False), name="today_task_client_uniq"
            ),
        ]
        indexes = [
            models.Index(
                fields=["plan", "position"],
                name="today_task_plan_pos_idx",
                condition=~Q(state="expired") & Q(deleted_at__isnull=True),
            ),
            models.Index(
                fields=["user_id", "local_date"], name="today_task_open_idx", condition=_in("state", c.OPEN_STATES)
            ),
            models.Index(fields=["user_id", "dedupe_key", "-local_date"], name="today_task_key_idx"),
            models.Index(
                fields=["user_id", "snoozed_until"], name="today_task_snooze_idx", condition=Q(state="snoozed")
            ),
        ]


class TaskEvidence(models.Model):
    """Idempotent record that an event contributed to a task. Unique per (task, event, key), so a replayed event adds nothing. Kept 90 days."""

    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name="evidence")
    user_id = models.UUIDField()
    event_name = models.CharField(max_length=64)
    event_key = models.CharField(max_length=120)
    delta = models.SmallIntegerField(default=0)  # progress contributed (answered count, cards reviewed)
    completes = models.BooleanField(default=False)  # the rule said done outright (exact match or reconcile)
    occurred_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "today_taskevidence"
        constraints = [
            models.UniqueConstraint(fields=["task", "event_name", "event_key"], name="today_evidence_once"),
        ]
        indexes = [models.Index(fields=["created_at"], name="today_evidence_created_idx")]

    def __str__(self) -> str:
        return f"{self.event_name}:{self.event_key} -> task {self.task_id}"


class TodaySettings(TimeStampedModel):
    """One row per student, created on first write. The time zone is the tracker's, not stored here."""

    user_id = models.UUIDField(primary_key=True)
    minutes_per_day = models.SmallIntegerField(null=True, blank=True)  # null = auto
    focus_papers = models.SmallIntegerField(null=True, blank=True)  # null = auto
    disabled_kinds = models.JSONField(default=list)  # kind names the student hid, at most 20 (checked in the service)
    show_tomorrow = models.BooleanField(default=True)
    celebrate = models.BooleanField(default=True)
    lite_mode = models.CharField(max_length=4, choices=_choices(c.LITE_MODES), default="auto")

    class Meta:
        db_table = "today_settings"
        constraints = [
            models.CheckConstraint(
                condition=Q(minutes_per_day__isnull=True)
                | Q(minutes_per_day__gte=c.SETTING_MINUTES_MIN, minutes_per_day__lte=c.SETTING_MINUTES_MAX),
                name="today_settings_minutes_range",
            ),
            models.CheckConstraint(
                condition=Q(focus_papers__isnull=True)
                | Q(focus_papers__gte=c.FOCUS_PAPERS_MIN, focus_papers__lte=c.FOCUS_PAPERS_SETTING_MAX),
                name="today_settings_focus_range",
            ),
            models.CheckConstraint(condition=_in("lite_mode", c.LITE_MODES), name="today_settings_lite_valid"),
        ]


class ProviderConfig(models.Model):
    """Operator switches, edited in the Django admin. A missing row means the defaults (enabled, weight 100). Cached 60 s in process."""

    provider = models.CharField(max_length=64, primary_key=True)  # the registered name
    enabled = models.BooleanField(default=True)
    weight_pct = models.SmallIntegerField(default=100)  # 0..300 multiplier in the score
    max_candidates = models.SmallIntegerField(null=True, blank=True)  # overrides the registered value, 1..50
    timeout_ms = models.SmallIntegerField(null=True, blank=True)  # overrides the registered value, 100..2000
    note = models.CharField(max_length=200, blank=True, default="")  # why it was changed
    updated_by = models.UUIDField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "today_providerconfig"
        constraints = [
            models.CheckConstraint(
                condition=Q(weight_pct__gte=0, weight_pct__lte=300), name="today_provcfg_weight_range"
            ),
            models.CheckConstraint(
                condition=Q(max_candidates__isnull=True) | Q(max_candidates__gte=1, max_candidates__lte=50),
                name="today_provcfg_max_range",
            ),
            models.CheckConstraint(
                condition=Q(timeout_ms__isnull=True) | Q(timeout_ms__gte=100, timeout_ms__lte=2000),
                name="today_provcfg_timeout_range",
            ),
        ]

    def __str__(self) -> str:
        return self.provider


# ---- R2: the study planner (ERD 2.6 to 2.8). Plain numbers and dates only: nothing the student typed is stored here. ------------


class StudyPlan(UUIDModel):
    """The student's date-driven plan for one enrolment. At most one `active` per student and enrolment (partial unique index).

    The numbers (`capacity_minutes`, `remaining_minutes`, `shortfall_minutes`) are what the pure planner computed at the last
    check; the database keeps them consistent (`shortfall = max(0, remaining - capacity)`) and never negative.
    """

    user_id = models.UUIDField()
    enrollment_id = models.UUIDField()  # by value (`coverage_enrollment.id`), validated through `coverage.selectors`
    scheme_id = models.UUIDField()  # by value: the scheme the plan was built on
    exam_date = models.DateField()
    daily_minutes = models.SmallIntegerField()
    utilisation_pct = models.SmallIntegerField(default=pc.UTILISATION_PCT_DEFAULT)
    status = models.CharField(max_length=10, choices=_choices(pc.PLAN_STATUSES), default="active")
    health = models.CharField(max_length=15, choices=_choices(pc.HEALTHS), default="unknown")
    capacity_minutes = models.IntegerField(default=0)
    remaining_minutes = models.IntegerField(default=0)
    shortfall_minutes = models.IntegerField(default=0)
    reading_deadline = models.DateField(null=True, blank=True)
    revise_until = models.DateField(null=True, blank=True)
    health_checked_at = models.DateTimeField(null=True, blank=True)
    last_replanned_at = models.DateTimeField(null=True, blank=True)
    replan_no = models.SmallIntegerField(default=0)
    params = models.JSONField(default=dict)  # {"v": 1, "learn_share": 70, "exam_week_days": 7, "lanes": 2}
    version = models.IntegerField(default=1)

    class Meta:
        db_table = "today_studyplan"
        constraints = [
            models.UniqueConstraint(
                fields=["user_id", "enrollment_id"],
                condition=Q(status="active"),
                name="today_studyplan_one_active",
            ),
            models.CheckConstraint(condition=_in("status", pc.PLAN_STATUSES), name="today_studyplan_status_valid"),
            models.CheckConstraint(condition=_in("health", pc.HEALTHS), name="today_studyplan_health_valid"),
            models.CheckConstraint(
                condition=Q(daily_minutes__gte=pc.DAILY_MINUTES_MIN, daily_minutes__lte=pc.DAILY_MINUTES_MAX),
                name="today_studyplan_daily_range",
            ),
            models.CheckConstraint(
                condition=Q(utilisation_pct__gte=pc.UTILISATION_PCT_MIN, utilisation_pct__lte=pc.UTILISATION_PCT_MAX),
                name="today_studyplan_util_range",
            ),
            models.CheckConstraint(
                condition=Q(capacity_minutes__gte=0, remaining_minutes__gte=0, shortfall_minutes__gte=0),
                name="today_studyplan_minutes_nonneg",
            ),
            models.CheckConstraint(
                condition=Q(shortfall_minutes=Greatest(Value(0), F("remaining_minutes") - F("capacity_minutes"))),
                name="today_studyplan_shortfall_exact",
            ),
            models.CheckConstraint(
                condition=Q(reading_deadline__isnull=True) | Q(reading_deadline__lte=F("exam_date")),
                name="today_studyplan_deadline_order",
            ),
            models.CheckConstraint(condition=_json_size_ok("params", 2048), name="today_studyplan_params_size"),
        ]
        indexes = [models.Index(fields=["user_id", "status"], name="today_splan_user_status_idx")]

    def __str__(self) -> str:
        return f"{self.user_id} plan for {self.exam_date} ({self.health})"


class Milestone(UUIDModel):
    """One dated goal of a plan: finish reading, first revision or a mock for a paper, or the plan's `exam_week`.

    `subject_key` is the stable key of the paper and survives a scheme switch; it is empty only for `exam_week`.
    `original_target_date` is the first date, so the screen can say "moved by 6 days".
    """

    plan = models.ForeignKey(StudyPlan, on_delete=models.CASCADE, related_name="milestones")
    user_id = models.UUIDField()
    subject = models.ForeignKey("syllabus.Subject", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    subject_key = models.CharField(max_length=80, blank=True, default="")  # as long as `syllabus_subject.key`
    kind = models.CharField(max_length=14, choices=_choices(pc.MILESTONE_KINDS))
    target_date = models.DateField()
    original_target_date = models.DateField()
    remaining_minutes = models.IntegerField(default=0)
    status = models.CharField(max_length=7, choices=_choices(pc.MILESTONE_STATUSES), default="pending")
    done_at = models.DateTimeField(null=True, blank=True)
    sort_order = models.SmallIntegerField(default=0)
    replan_no = models.SmallIntegerField(default=0)  # the plan revision that last changed it

    class Meta:
        db_table = "today_milestone"
        constraints = [
            models.UniqueConstraint(fields=["plan", "kind", "subject_key"], name="today_milestone_once"),
            models.CheckConstraint(condition=_in("kind", pc.MILESTONE_KINDS), name="today_milestone_kind_valid"),
            models.CheckConstraint(condition=_in("status", pc.MILESTONE_STATUSES), name="today_milestone_status_valid"),
            models.CheckConstraint(condition=Q(remaining_minutes__gte=0), name="today_milestone_minutes_nonneg"),
            models.CheckConstraint(
                condition=(Q(kind="exam_week") & Q(subject_key="")) | (~Q(kind="exam_week") & ~Q(subject_key="")),
                name="today_milestone_key_matches_kind",
            ),
            models.CheckConstraint(
                condition=(Q(status="done") & Q(done_at__isnull=False)) | (~Q(status="done") & Q(done_at__isnull=True)),
                name="today_milestone_done_at_matches",
            ),
        ]
        indexes = [
            models.Index(
                fields=["user_id", "target_date"],
                name="today_milestone_open_idx",
                condition=_in("status", pc.OPEN_MILESTONE_STATUSES),
            )
        ]

    def __str__(self) -> str:
        return f"{self.kind} {self.subject_key or 'plan'} on {self.target_date}"


class ReplanEvent(models.Model):
    """Audit of one re-plan, so the student can see what moved and support can explain it. `option_chosen` is NULL while the options are pending."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    plan = models.ForeignKey(StudyPlan, on_delete=models.CASCADE, related_name="replan_events")
    user_id = models.UUIDField()
    trigger = models.CharField(max_length=13, choices=_choices(pc.REPLAN_TRIGGERS))
    health_before = models.CharField(max_length=15, choices=_choices(pc.HEALTHS))
    health_after = models.CharField(max_length=15, choices=_choices(pc.HEALTHS))
    shortfall_before = models.IntegerField(default=0)
    shortfall_after = models.IntegerField(default=0)
    moved_count = models.SmallIntegerField(default=0)
    option_chosen = models.CharField(max_length=15, null=True, blank=True, choices=_choices(pc.OPTION_CHOICES))  # noqa: DJ001 - NULL while pending; "" is not a choice
    summary = models.JSONField(default=dict)  # {"v": 1, "moved": [...], "options": [...]}, at most 8 KB
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "today_replanevent"
        constraints = [
            models.CheckConstraint(condition=_in("trigger", pc.REPLAN_TRIGGERS), name="today_replan_trigger_valid"),
            models.CheckConstraint(condition=_in("health_before", pc.HEALTHS), name="today_replan_before_valid"),
            models.CheckConstraint(condition=_in("health_after", pc.HEALTHS), name="today_replan_after_valid"),
            models.CheckConstraint(
                condition=Q(option_chosen__isnull=True) | _in("option_chosen", pc.OPTION_CHOICES),
                name="today_replan_option_valid",
            ),
            models.CheckConstraint(
                condition=Q(shortfall_before__gte=0, shortfall_after__gte=0, moved_count__gte=0),
                name="today_replan_numbers_nonneg",
            ),
            models.CheckConstraint(
                condition=_json_size_ok("summary", pc.SUMMARY_MAX_CHARS), name="today_replan_summary_size"
            ),
        ]
        indexes = [models.Index(fields=["plan", "-created_at"], name="today_replan_plan_created_idx")]

    def __str__(self) -> str:
        return f"{self.trigger}: {self.health_before} -> {self.health_after}"


class DayFeedback(UUIDModel):
    """The student's one-tap answer for a day: too much, just right or too little. One per day plan. `consumed` rows have already
    been used (or dismissed) in a budget suggestion, so the same three answers never suggest twice."""

    user_id = models.UUIDField()
    plan = models.OneToOneField(DayPlan, on_delete=models.CASCADE, related_name="feedback")
    local_date = models.DateField()
    rating = models.CharField(max_length=10, choices=_choices(c.FEEDBACK_RATINGS))
    consumed = models.BooleanField(default=False)

    class Meta:
        db_table = "today_dayfeedback"
        constraints = [
            models.CheckConstraint(condition=_in("rating", c.FEEDBACK_RATINGS), name="today_feedback_rating")
        ]
        indexes = [models.Index(fields=["user_id", "-local_date"], name="today_feedback_user_date_idx")]

    def __str__(self) -> str:
        return f"{self.local_date}: {self.rating}"
