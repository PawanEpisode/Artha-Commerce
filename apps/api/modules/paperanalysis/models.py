"""
Data models for Paper Analysis and Recommendation Engine (F-11).
Reference: ERD section 2.
"""

from __future__ import annotations

from decimal import Decimal

from django.db import models

from core.models import UUIDModel


class Paper(UUIDModel):
    class PaperKind(models.TextChoices):
        EXAM = "exam", "Exam Sitting"
        MTP = "mtp", "Mock Test Paper"
        RTP = "rtp", "Revision Test Paper"
        SAMPLE = "sample", "Sample Paper"

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        IN_REVIEW = "in_review", "In Review"
        PUBLISHED = "published", "Published"
        UNPUBLISHED = "unpublished", "Unpublished"
        EXCLUDED = "excluded", "Excluded"

    class EntryMode(models.TextChoices):
        FROM_BANK = "from_bank", "From Question Bank"
        SKELETON = "skeleton", "Skeleton Structure"

    class OriginModule(models.TextChoices):
        PYQ = "pyq", "Previous Year Questions"
        MTP = "mtp", "Mock Test Papers"
        SKELETON = "skeleton", "Skeleton Entry"

    subject = models.ForeignKey("syllabus.Subject", on_delete=models.PROTECT, related_name="papers")
    scheme = models.ForeignKey("syllabus.Scheme", on_delete=models.PROTECT, related_name="+")
    level = models.ForeignKey("syllabus.Level", on_delete=models.PROTECT, related_name="+")
    subject_key = models.CharField(max_length=80)
    term_code = models.CharField(max_length=16)
    exam_term = models.ForeignKey("syllabus.ExamTerm", null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    term_sort = models.DateField()
    paper_kind = models.CharField(max_length=16, choices=PaperKind.choices, default=PaperKind.EXAM)
    series = models.CharField(max_length=32, blank=True, default="")
    title = models.CharField(max_length=200)
    entry_mode = models.CharField(max_length=16, choices=EntryMode.choices, default=EntryMode.SKELETON)
    origin_module = models.CharField(max_length=16, choices=OriginModule.choices, default=OriginModule.SKELETON)
    origin_ref = models.CharField(max_length=64, null=True, blank=True)  # noqa: DJ001
    source_url = models.URLField(max_length=500, blank=True, default="")
    total_marks = models.DecimalField(max_digits=6, decimal_places=1)
    duration_minutes = models.SmallIntegerField(null=True, blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.DRAFT)
    is_limited = models.BooleanField(default=False)
    exception_note = models.TextField(null=True, blank=True)  # noqa: DJ001
    include_in_stats = models.BooleanField(default=True)
    excluded_reason = models.TextField(null=True, blank=True)  # noqa: DJ001
    question_count = models.SmallIntegerField(default=0)
    confirmed_marks = models.DecimalField(max_digits=6, decimal_places=1, default=Decimal("0.0"))
    marks_objective = models.DecimalField(max_digits=6, decimal_places=1, default=Decimal("0.0"))
    marks_descriptive = models.DecimalField(max_digits=6, decimal_places=1, default=Decimal("0.0"))
    marks_theory = models.DecimalField(max_digits=6, decimal_places=1, default=Decimal("0.0"))
    marks_practical = models.DecimalField(max_digits=6, decimal_places=1, default=Decimal("0.0"))
    marks_optional_offered = models.DecimalField(max_digits=6, decimal_places=1, default=Decimal("0.0"))
    marks_attemptable = models.DecimalField(max_digits=6, decimal_places=1, default=Decimal("0.0"))
    rev = models.IntegerField(default=1)
    published_at = models.DateTimeField(null=True, blank=True)
    published_by = models.UUIDField(null=True, blank=True)
    created_by = models.UUIDField()

    class Meta:
        db_table = "paperanalysis_paper"
        constraints = [
            models.UniqueConstraint(
                fields=["scheme", "subject_key", "term_code", "paper_kind", "series"],
                name="uq_pa_paper_sittings",
            ),
            models.CheckConstraint(
                condition=models.Q(total_marks__gt=Decimal("0")),
                name="ck_pa_paper_total_marks_positive",
            ),
        ]
        indexes = [
            models.Index(fields=["subject_key", "scheme", "-term_sort"], name="idx_pa_paper_stats_window"),
            models.Index(fields=["status", "-updated_at"], name="idx_pa_paper_status_upd"),
            models.Index(fields=["origin_module", "origin_ref"], name="idx_pa_paper_origin"),
        ]

    def __str__(self) -> str:
        return f"{self.title} ({self.status})"


class ChoiceGroup(UUIDModel):
    paper = models.ForeignKey(Paper, on_delete=models.CASCADE, related_name="choice_groups")
    label = models.CharField(max_length=64)
    pick_n = models.SmallIntegerField()
    of_m = models.SmallIntegerField()
    note = models.TextField(blank=True, default="")

    class Meta:
        db_table = "paperanalysis_choicegroup"
        constraints = [
            models.UniqueConstraint(fields=["paper", "label"], name="uq_pa_cg_paper_label"),
            models.CheckConstraint(
                condition=models.Q(pick_n__gte=1, of_m__gte=models.F("pick_n")),
                name="ck_pa_cg_bounds",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.label} (pick {self.pick_n} of {self.of_m})"


class PaperQuestion(UUIDModel):
    class AllocState(models.TextChoices):
        UNTAGGED = "untagged", "Untagged"
        SUGGESTED = "suggested", "Suggested"
        CONFIRMED = "confirmed", "Confirmed"
        DISPUTED = "disputed", "Disputed"

    class QaState(models.TextChoices):
        NOT_SAMPLED = "not_sampled", "Not Sampled"
        QUEUED = "queued", "Queued for Review"
        AGREED = "agreed", "Agreed"
        DISPUTED = "disputed", "Disputed"

    paper = models.ForeignKey(Paper, on_delete=models.CASCADE, related_name="questions")
    label = models.CharField(max_length=64)
    position = models.SmallIntegerField()
    question_id = models.UUIDField(null=True, blank=True)
    question_version_id = models.UUIDField(null=True, blank=True)
    marks = models.DecimalField(max_digits=5, decimal_places=1)
    choice_group = models.ForeignKey(ChoiceGroup, null=True, blank=True, on_delete=models.SET_NULL, related_name="questions")
    effective_marks = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal("0.00"))
    format = models.CharField(max_length=32)
    nature = models.CharField(max_length=32, null=True, blank=True)  # noqa: DJ001
    section_label = models.CharField(max_length=64, blank=True, default="")
    source_ref = models.CharField(max_length=120, blank=True, default="")
    tag_hint = models.TextField(null=True, blank=True)  # noqa: DJ001
    text_available = models.BooleanField(default=True)
    alloc_state = models.CharField(max_length=16, choices=AllocState.choices, default=AllocState.UNTAGGED)
    confirmed_by = models.UUIDField(null=True, blank=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    qa_state = models.CharField(max_length=16, choices=QaState.choices, default=QaState.NOT_SAMPLED)
    qa_by = models.UUIDField(null=True, blank=True)
    client_id = models.UUIDField(null=True, blank=True)
    rev = models.IntegerField(default=1)

    class Meta:
        db_table = "paperanalysis_paperquestion"
        constraints = [
            models.UniqueConstraint(fields=["paper", "label"], name="uq_pa_pq_paper_label"),
            models.UniqueConstraint(fields=["paper", "position"], name="uq_pa_pq_paper_pos"),
            models.CheckConstraint(condition=models.Q(marks__gt=Decimal("0")), name="ck_pa_pq_marks_positive"),
        ]
        indexes = [
            models.Index(fields=["paper", "alloc_state"], name="idx_pa_pq_state"),
            models.Index(fields=["question_id"], name="idx_pa_pq_qid"),
            models.Index(fields=["qa_state"], name="idx_pa_pq_qa"),
        ]

    def __str__(self) -> str:
        return f"Q{self.label} ({self.marks}m)"


class Allocation(UUIDModel):
    class Status(models.TextChoices):
        SUGGESTED = "suggested", "Suggested"
        CONFIRMED = "confirmed", "Confirmed"
        REJECTED = "rejected", "Rejected"
        DISPUTED = "disputed", "Disputed"

    class Origin(models.TextChoices):
        BANK_MAPPING = "bank_mapping", "From Question Bank Mapping"
        AI = "ai", "AI Suggested"
        EDITOR = "editor", "Human Editor"
        IMPORT = "import", "Imported"
        REMAP = "remap", "Scheme Remap"

    class Basis(models.TextChoices):
        SINGLE = "single", "Single Chapter"
        EVEN = "even", "Even Split"
        WEIGHTED = "weighted", "Weighted Split"
        MANUAL = "manual", "Manual Entry"

    paper_question = models.ForeignKey(PaperQuestion, on_delete=models.CASCADE, related_name="allocations")
    chapter = models.ForeignKey("syllabus.Chapter", on_delete=models.PROTECT, related_name="+")
    topic = models.ForeignKey("syllabus.Topic", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    subject = models.ForeignKey("syllabus.Subject", on_delete=models.PROTECT, related_name="+")
    scheme = models.ForeignKey("syllabus.Scheme", on_delete=models.PROTECT, related_name="+")
    subject_key = models.CharField(max_length=80)
    chapter_key = models.CharField(max_length=100)
    marks = models.DecimalField(max_digits=5, decimal_places=2)
    share = models.DecimalField(max_digits=4, decimal_places=3, default=Decimal("1.000"))
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.SUGGESTED)
    origin = models.CharField(max_length=16, choices=Origin.choices, default=Origin.EDITOR)
    basis = models.CharField(max_length=16, choices=Basis.choices, default=Basis.MANUAL)
    confidence = models.DecimalField(max_digits=3, decimal_places=2, null=True, blank=True)
    rationale = models.CharField(max_length=200, null=True, blank=True)  # noqa: DJ001
    ai_call_ref = models.UUIDField(null=True, blank=True)
    model = models.CharField(max_length=64, null=True, blank=True)  # noqa: DJ001
    prompt_version = models.CharField(max_length=32, null=True, blank=True)  # noqa: DJ001
    suggested_at = models.DateTimeField(null=True, blank=True)
    decided_by = models.UUIDField(null=True, blank=True)
    decided_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "paperanalysis_allocation"
        constraints = [
            models.CheckConstraint(condition=models.Q(marks__gt=Decimal("0")), name="ck_pa_alloc_marks_pos"),
        ]
        indexes = [
            models.Index(fields=["chapter", "status"], name="idx_pa_alloc_ch_stat"),
            models.Index(fields=["status", "origin"], name="idx_pa_alloc_stat_orig"),
        ]

    def __str__(self) -> str:
        return f"{self.chapter_key}: {self.marks}m ({self.status})"


class AllocationAudit(models.Model):
    id = models.BigAutoField(primary_key=True)
    paper_question_id = models.UUIDField(db_index=True)
    allocation_id = models.UUIDField(null=True, blank=True)
    action = models.CharField(max_length=32)
    actor_id = models.UUIDField(null=True, blank=True)
    before = models.JSONField(null=True, blank=True)
    after = models.JSONField(null=True, blank=True)
    reason = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "paperanalysis_allocationaudit"
        indexes = [
            models.Index(fields=["paper_question_id", "created_at"], name="idx_pa_audit_pq_created"),
            models.Index(fields=["actor_id", "created_at"], name="idx_pa_audit_actor_created"),
        ]

    def __str__(self) -> str:
        return f"Audit({self.action} on PQ {self.paper_question_id})"


class TermChapterStat(models.Model):
    paper = models.ForeignKey(Paper, on_delete=models.CASCADE, related_name="term_chapter_stats")
    chapter = models.ForeignKey("syllabus.Chapter", on_delete=models.CASCADE, related_name="+")
    scheme = models.ForeignKey("syllabus.Scheme", on_delete=models.CASCADE, related_name="+")
    subject_key = models.CharField(max_length=80)
    chapter_key = models.CharField(max_length=100)
    term_code = models.CharField(max_length=16)
    term_sort = models.DateField()
    paper_kind = models.CharField(max_length=16)
    marks_offered = models.DecimalField(max_digits=6, decimal_places=2)
    marks_effective = models.DecimalField(max_digits=6, decimal_places=2)
    marks_compulsory = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal("0.00"))
    marks_objective = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal("0.00"))
    marks_descriptive = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal("0.00"))
    marks_theory = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal("0.00"))
    marks_practical = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal("0.00"))
    question_count = models.SmallIntegerField(default=0)
    stats_version = models.BigIntegerField()

    class Meta:
        db_table = "paperanalysis_termchapterstat"
        constraints = [
            models.UniqueConstraint(fields=["paper", "chapter"], name="uq_pa_tcs_paper_chap"),
        ]
        indexes = [
            models.Index(fields=["chapter", "-term_sort"], name="idx_pa_tcs_ch_sort"),
            models.Index(fields=["scheme", "subject_key", "-term_sort"], name="idx_pa_tcs_subj_sort"),
        ]

    def __str__(self) -> str:
        return f"{self.chapter_key} in {self.term_code}: {self.marks_effective}m"


class ChapterAggregate(models.Model):
    chapter = models.ForeignKey("syllabus.Chapter", on_delete=models.CASCADE, related_name="+")
    view_key = models.CharField(max_length=32, default="w6-p0-o1")
    scheme = models.ForeignKey("syllabus.Scheme", on_delete=models.CASCADE, related_name="+")
    subject_key = models.CharField(max_length=80)
    chapter_key = models.CharField(max_length=100)
    papers_considered = models.SmallIntegerField(default=0)
    asked_n = models.SmallIntegerField(default=0)
    avg_effective = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal("0.00"))
    avg_when_asked = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    max_effective = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    last_asked_term_code = models.CharField(max_length=16, null=True, blank=True)  # noqa: DJ001
    share_of_marks = models.DecimalField(max_digits=5, decimal_places=4, null=True, blank=True)
    trend = models.DecimalField(max_digits=4, decimal_places=3, null=True, blank=True)
    comparability = models.CharField(max_length=16, default="native")
    carried_papers = models.SmallIntegerField(default=0)
    weight_basis = models.CharField(max_length=16, default="inferred")
    stats_version = models.BigIntegerField(default=0)
    inputs_hash = models.CharField(max_length=64, default="")
    computed_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "paperanalysis_chapteraggregate"
        constraints = [
            models.UniqueConstraint(fields=["chapter", "view_key"], name="uq_pa_ca_chap_view"),
        ]
        indexes = [
            models.Index(fields=["subject_key", "scheme", "view_key"], name="idx_pa_ca_subj_view"),
        ]

    def __str__(self) -> str:
        return f"Agg({self.chapter_key}, {self.view_key}): avg {self.avg_effective}"


class TopicStat(models.Model):
    topic = models.ForeignKey("syllabus.Topic", on_delete=models.CASCADE, related_name="+")
    view_key = models.CharField(max_length=32, default="w6-p0-o1")
    chapter = models.ForeignKey("syllabus.Chapter", on_delete=models.CASCADE, related_name="+")
    scheme = models.ForeignKey("syllabus.Scheme", on_delete=models.CASCADE, related_name="+")
    papers_considered = models.SmallIntegerField(default=0)
    asked_n = models.SmallIntegerField(default=0)
    last_asked_term_code = models.CharField(max_length=16, null=True, blank=True)  # noqa: DJ001
    stats_version = models.BigIntegerField(default=0)
    computed_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "paperanalysis_topicstat"
        constraints = [
            models.UniqueConstraint(fields=["topic", "view_key"], name="uq_pa_ts_top_view"),
        ]
        indexes = [
            models.Index(fields=["chapter", "view_key"], name="idx_pa_ts_ch_view"),
        ]

    def __str__(self) -> str:
        return f"TopicStat({self.topic_id}): asked {self.asked_n}"


class SubjectState(models.Model):
    subject = models.OneToOneField("syllabus.Subject", primary_key=True, on_delete=models.CASCADE, related_name="paperanalysis_state")
    scheme = models.ForeignKey("syllabus.Scheme", on_delete=models.CASCADE, related_name="+")
    subject_key = models.CharField(max_length=80)
    stats_version = models.BigIntegerField(default=0)
    papers_published = models.SmallIntegerField(default=0)
    exam_papers_published = models.SmallIntegerField(default=0)
    papers_target = models.SmallIntegerField(default=10)
    data_status = models.CharField(max_length=16, default="insufficient")
    withheld_reason = models.CharField(max_length=64, null=True, blank=True)  # noqa: DJ001
    last_backtest_id = models.UUIDField(null=True, blank=True)
    seo_indexable = models.BooleanField(default=False)
    min_papers_override = models.SmallIntegerField(null=True, blank=True)
    updated_by = models.UUIDField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "paperanalysis_subjectstate"

    def __str__(self) -> str:
        return f"State({self.subject_key}): v{self.stats_version} {self.data_status}"


class WeightSet(UUIDModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        ACTIVE = "active", "Active"
        RETIRED = "retired", "Retired"

    name = models.CharField(max_length=120)
    engine_version = models.CharField(max_length=16, default="ps-1")
    scope_course = models.ForeignKey("syllabus.Course", null=True, blank=True, on_delete=models.CASCADE, related_name="+")
    scope_level = models.ForeignKey("syllabus.Level", null=True, blank=True, on_delete=models.CASCADE, related_name="+")
    params = models.JSONField(default=dict)
    params_schema = models.SmallIntegerField(default=1)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.DRAFT)
    notes = models.TextField(blank=True, default="")
    created_by = models.UUIDField(null=True, blank=True)
    activated_by = models.UUIDField(null=True, blank=True)
    activated_at = models.DateTimeField(null=True, blank=True)
    retired_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "paperanalysis_weightset"

    def __str__(self) -> str:
        return f"{self.name} ({self.engine_version}, {self.status})"


class BacktestRun(UUIDModel):
    class Status(models.TextChoices):
        QUEUED = "queued", "Queued"
        RUNNING = "running", "Running"
        DONE = "done", "Done"
        FAILED = "failed", "Failed"

    weightset = models.ForeignKey(WeightSet, on_delete=models.CASCADE, related_name="backtests")
    engine_version = models.CharField(max_length=16, default="ps-1")
    subject = models.ForeignKey("syllabus.Subject", on_delete=models.CASCADE, related_name="+")
    scheme = models.ForeignKey("syllabus.Scheme", on_delete=models.CASCADE, related_name="+")
    k_fraction = models.DecimalField(max_digits=3, decimal_places=2, default=Decimal("0.30"))
    papers_used = models.SmallIntegerField(default=0)
    folds = models.SmallIntegerField(default=0)
    marks_captured = models.DecimalField(max_digits=5, decimal_places=4, null=True, blank=True)
    baseline_flat = models.DecimalField(max_digits=5, decimal_places=4, default=Decimal("0.3000"))
    baseline_last_paper = models.DecimalField(max_digits=5, decimal_places=4, null=True, blank=True)
    lift = models.DecimalField(max_digits=5, decimal_places=3, null=True, blank=True)
    metrics = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.QUEUED)
    job_id = models.UUIDField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    created_by = models.UUIDField(null=True, blank=True)

    class Meta:
        db_table = "paperanalysis_backtestrun"
        indexes = [
            models.Index(fields=["subject", "-created_at"], name="idx_pa_bt_subj_date"),
        ]

    def __str__(self) -> str:
        return f"Backtest({self.id}, lift={self.lift})"


class Settings(models.Model):
    user_id = models.UUIDField(primary_key=True)
    window = models.SmallIntegerField(default=6)
    include_practice = models.BooleanField(default=False)
    include_older = models.BooleanField(default=True)
    show_reasons_default = models.BooleanField(default=True)
    hide_tiers = models.BooleanField(default=False)
    default_hours_per_day = models.DecimalField(max_digits=3, decimal_places=1, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "paperanalysis_settings"

    def __str__(self) -> str:
        return f"Settings({self.user_id})"


class Snapshot(UUIDModel):
    user_id = models.UUIDField(db_index=True)
    enrollment_id = models.UUIDField(db_index=True)
    scope_key = models.CharField(max_length=120)
    engine_version = models.CharField(max_length=16, default="ps-1")
    weightset = models.ForeignKey(WeightSet, on_delete=models.CASCADE, related_name="+")
    inputs_hash = models.CharField(max_length=64)
    inputs_summary = models.JSONField(default=dict)
    results = models.JSONField(default=dict)
    results_schema = models.SmallIntegerField(default=1)
    data_status = models.CharField(max_length=16)
    expires_at = models.DateTimeField()

    class Meta:
        db_table = "paperanalysis_snapshot"
        constraints = [
            models.UniqueConstraint(
                fields=["user_id", "enrollment_id", "scope_key", "inputs_hash"],
                name="uq_pa_snap_hash",
            ),
        ]
        indexes = [
            models.Index(fields=["user_id", "enrollment_id", "scope_key", "-created_at"], name="idx_pa_snap_latest"),
            models.Index(fields=["expires_at"], name="idx_pa_snap_exp"),
        ]

    def __str__(self) -> str:
        return f"Snapshot({self.id}, {self.scope_key})"


class Plan(UUIDModel):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        COMPLETED = "completed", "Completed"
        ENDED = "ended", "Ended"
        SUPERSEDED = "superseded", "Superseded"

    user_id = models.UUIDField(db_index=True)
    enrollment_id = models.UUIDField(db_index=True)
    client_id = models.UUIDField()
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.ACTIVE)
    days = models.SmallIntegerField()
    hours_per_day = models.DecimalField(max_digits=3, decimal_places=1)
    tz = models.CharField(max_length=64, default="Asia/Kolkata")
    start_date = models.DateField()
    end_date = models.DateField()
    subject_keys = models.JSONField(default=list)
    balance_subjects = models.BooleanField(default=False)
    snapshot = models.ForeignKey(Snapshot, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    engine_version = models.CharField(max_length=16, default="ps-1")
    weightset = models.ForeignKey(WeightSet, on_delete=models.CASCADE, related_name="+")
    summary = models.JSONField(default=dict)
    parent_plan = models.ForeignKey("self", null=True, blank=True, on_delete=models.SET_NULL, related_name="replans")
    ended_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "paperanalysis_plan"
        constraints = [
            models.UniqueConstraint(fields=["user_id", "client_id"], name="uq_pa_plan_client"),
        ]
        indexes = [
            models.Index(fields=["user_id", "-created_at"], name="idx_pa_plan_user_date"),
        ]

    def __str__(self) -> str:
        return f"Plan({self.id}, status={self.status})"


class PlanItem(UUIDModel):
    class Mode(models.TextChoices):
        FULL = "full", "Full Study"
        KEY_POINTS = "key_points", "Key Points Only"

    class State(models.TextChoices):
        PLANNED = "planned", "Planned"
        DONE = "done", "Done"
        SKIPPED = "skipped", "Skipped"

    plan = models.ForeignKey(Plan, on_delete=models.CASCADE, related_name="items")
    user_id = models.UUIDField(db_index=True)
    chapter = models.ForeignKey("syllabus.Chapter", on_delete=models.PROTECT, related_name="+")
    subject_key = models.CharField(max_length=80)
    chapter_key = models.CharField(max_length=100)
    planned_date = models.DateField()
    position = models.SmallIntegerField(default=0)
    minutes = models.SmallIntegerField()
    mode = models.CharField(max_length=16, choices=Mode.choices, default=Mode.FULL)
    expected_gain = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("0.00"))
    mph = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("0.00"))
    state = models.CharField(max_length=16, choices=State.choices, default=State.PLANNED)
    done_at = models.DateTimeField(null=True, blank=True)
    moved_from = models.DateField(null=True, blank=True)

    class Meta:
        db_table = "paperanalysis_planitem"
        constraints = [
            models.UniqueConstraint(fields=["plan", "chapter"], name="uq_pa_pi_plan_chap"),
        ]
        indexes = [
            models.Index(fields=["plan", "planned_date", "position"], name="idx_pa_pi_plan_pos"),
            models.Index(fields=["user_id", "planned_date"], name="idx_pa_pi_user_date"),
        ]

    def __str__(self) -> str:
        return f"{self.chapter_key} on {self.planned_date} ({self.state})"


class Flag(UUIDModel):
    class Source(models.TextChoices):
        STUDENT = "student", "Student"
        SYSTEM = "system", "System Drift"

    class TargetType(models.TextChoices):
        ALLOCATION = "allocation", "Allocation"
        PAPER = "paper", "Paper"
        RECOMMENDATION = "recommendation", "Recommendation"
        DRIFT = "drift", "Drift"

    class Status(models.TextChoices):
        OPEN = "open", "Open"
        ACCEPTED = "accepted", "Accepted"
        REJECTED = "rejected", "Rejected"
        DUPLICATE = "duplicate", "Duplicate"

    user_id = models.UUIDField(null=True, blank=True)
    source = models.CharField(max_length=16, choices=Source.choices, default=Source.STUDENT)
    target_type = models.CharField(max_length=32, choices=TargetType.choices)
    target_id = models.UUIDField()
    note = models.TextField(blank=True, default="")
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.OPEN)
    resolved_by = models.UUIDField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "paperanalysis_flag"
        indexes = [
            models.Index(fields=["status", "created_at"], name="idx_pa_flag_stat_date"),
        ]

    def __str__(self) -> str:
        return f"Flag({self.target_type}:{self.target_id}, {self.status})"
