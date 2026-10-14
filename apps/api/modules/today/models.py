"""
Tables for Today (F-13 R1, ERD section 2). Today stores decisions, not knowledge: a task row is a snapshot of one offer made to
one student on one day; the truth about the underlying work stays in the owning module. `user_id` holds the Supabase user id by
value (no cross-schema foreign key). `subject_id` and `chapter_id` are real foreign keys that become NULL if the syllabus row is
removed; the stable `subject_key` and `chapter_key` copies keep links working across a scheme switch.

Counters on `DayPlan` are recomputed from the tasks under the plan lock, never incremented (ERD 0.6).
"""

from django.db import models
from django.db.models import Q, TextField
from django.db.models.functions import Cast, Length
from django.db.models.lookups import LessThanOrEqual

from core.models import TimeStampedModel, UUIDModel

from .domain import constants as c


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
