"""
MCQ Bank models (F-05 ERD sections 2.1-2.7).
Thin module: sets, verified pattern profiles, test presets, self-reported external logs,
reference links, and adaptive practice runs. Questions and attempts live strictly in F-06.
"""

from __future__ import annotations

from decimal import Decimal

from django.db import models
from django.db.models import Q
from django.utils import timezone

from core.models import UUIDModel


class McqSet(UUIDModel):
    """A catalogue entry for an MCQ set. Either hosted (F-06 collection) or link_out (Institute/external)."""

    class SetKind(models.TextChoices):
        INSTITUTE_MCQ = "institute_mcq", "Institute MCQ"
        RTP = "rtp", "RTP"
        MTP = "mtp", "MTP"
        COACHING = "coaching", "Coaching"
        PLATFORM = "platform", "Platform"

    class Delivery(models.TextChoices):
        HOSTED = "hosted", "Hosted"
        LINK_OUT = "link_out", "Link Out"

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PUBLISHED = "published", "Published"
        WITHDRAWN = "withdrawn", "Withdrawn"

    class LinkStatus(models.TextChoices):
        UNCHECKED = "unchecked", "Unchecked"
        OK = "ok", "OK"
        FAILING = "failing", "Failing"
        BROKEN = "broken", "Broken"

    slug = models.SlugField(max_length=80, unique=True)
    title = models.CharField(max_length=120)
    description = models.TextField(blank=True, default="")
    set_kind = models.CharField(max_length=32, choices=SetKind.choices, default=SetKind.PLATFORM)
    delivery = models.CharField(max_length=16, choices=Delivery.choices, default=Delivery.LINK_OUT)

    collection = models.ForeignKey(
        "questionbank.Collection",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="mcq_sets",
    )
    source_name = models.CharField(max_length=120, blank=True, default="")
    source_kind = models.CharField(max_length=32, default="platform")
    source_url = models.URLField(blank=True, default="")
    source_ref = models.CharField(max_length=120, blank=True, default="")

    course = models.ForeignKey("syllabus.Course", on_delete=models.PROTECT, related_name="mcq_sets")
    level = models.ForeignKey("syllabus.Level", on_delete=models.PROTECT, related_name="mcq_sets")
    subject_key = models.CharField(max_length=80)
    subject = models.ForeignKey(
        "syllabus.Subject", null=True, blank=True, on_delete=models.PROTECT, related_name="mcq_sets"
    )
    chapter_key = models.CharField(max_length=80, blank=True, default="")
    chapter = models.ForeignKey(
        "syllabus.Chapter", null=True, blank=True, on_delete=models.PROTECT, related_name="mcq_sets"
    )
    term_code = models.CharField(max_length=16, blank=True, default="")

    question_count = models.IntegerField(null=True, blank=True)
    est_minutes = models.SmallIntegerField(null=True, blank=True)
    license_tier = models.CharField(max_length=32, default="link_only")
    rights_basis = models.CharField(max_length=32, blank=True, default="")
    rights_note = models.TextField(blank=True, default="")
    ingestion_item_id = models.UUIDField(null=True, blank=True)

    status = models.CharField(max_length=16, choices=Status.choices, default=Status.DRAFT)
    withdrawn_reason = models.CharField(max_length=32, blank=True, default="")
    link_status = models.CharField(max_length=16, choices=LinkStatus.choices, default=LinkStatus.UNCHECKED)
    link_checked_at = models.DateTimeField(null=True, blank=True)
    link_fail_count = models.SmallIntegerField(default=0)

    verified = models.BooleanField(default=False)
    verified_by = models.UUIDField(null=True, blank=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    featured = models.BooleanField(default=False)
    sort_order = models.SmallIntegerField(default=0)
    published_at = models.DateTimeField(null=True, blank=True)
    created_by = models.UUIDField(null=True, blank=True)

    class Meta:
        db_table = "mcqbank_set"
        ordering = ["sort_order", "title"]
        indexes = [
            models.Index(fields=["subject", "status", "sort_order"], name="mcqset_subj_st_ord_idx"),
            models.Index(fields=["course", "level", "subject_key", "-term_code"], name="mcqset_crs_lvl_trm_idx"),
            models.Index(fields=["link_status", "link_checked_at"], name="mcqset_lnk_st_chk_idx"),
            models.Index(fields=["chapter"], name="mcqset_chapter_idx"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["collection"],
                condition=Q(collection__isnull=False) & ~Q(status="withdrawn"),
                name="mcqset_unique_live_collection",
            )
        ]

    def __str__(self) -> str:
        return f"{self.title} ({self.delivery})"


class PatternProfile(UUIDModel):
    """The MCQ structure of one paper according to official exam patterns."""

    class Format(models.TextChoices):
        ALL_MCQ = "all_mcq", "All MCQ"
        MCQ_SECTION = "mcq_section", "MCQ Section"

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        ACTIVE = "active", "Active"
        RETIRED = "retired", "Retired"

    course = models.ForeignKey("syllabus.Course", on_delete=models.PROTECT, related_name="pattern_profiles")
    level = models.ForeignKey("syllabus.Level", on_delete=models.PROTECT, related_name="pattern_profiles")
    subject_key = models.CharField(max_length=80)
    scheme = models.ForeignKey(
        "syllabus.Scheme", null=True, blank=True, on_delete=models.PROTECT, related_name="pattern_profiles"
    )
    effective_from = models.DateField()
    effective_to = models.DateField(null=True, blank=True)
    format = models.CharField(max_length=20, choices=Format.choices, default=Format.ALL_MCQ)
    mcq_count = models.SmallIntegerField()
    mcq_total_marks = models.DecimalField(max_digits=6, decimal_places=1)
    marks_per_mcq = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)
    minutes = models.SmallIntegerField(null=True, blank=True)
    case_scenario_count = models.SmallIntegerField(null=True, blank=True)

    status = models.CharField(max_length=16, choices=Status.choices, default=Status.DRAFT)
    verified = models.BooleanField(default=False)
    source_note = models.TextField(blank=True, default="")
    source_url = models.URLField(blank=True, default="")
    verified_by = models.UUIDField(null=True, blank=True)
    verified_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "mcqbank_patternprofile"
        ordering = ["-effective_from"]
        constraints = [
            models.UniqueConstraint(
                fields=["course", "level", "subject_key", "effective_from"],
                name="mcqpattern_unique_eff_from",
            ),
            models.CheckConstraint(
                condition=Q(mcq_count__gte=1, mcq_count__lte=200),
                name="mcqpattern_count_range",
            ),
        ]
        indexes = [
            models.Index(
                fields=["course", "level", "subject_key", "-effective_from"],
                name="mcqpattern_resolution_idx",
            )
        ]

    def __str__(self) -> str:
        return f"{self.subject_key} pattern ({self.mcq_count} MCQs, {self.mcq_total_marks} marks)"


class TestPreset(UUIDModel):
    """Preset configuration for launching a practice session."""

    __test__ = False

    class Kind(models.TextChoices):
        BUILDER = "builder", "Builder"
        BLUEPRINT = "blueprint", "Blueprint"
        PATTERN = "pattern", "Pattern"

    user_id = models.UUIDField(null=True, blank=True, db_index=True)
    is_system = models.BooleanField(default=False)
    scope_key = models.CharField(max_length=80, blank=True, default="")
    name = models.CharField(max_length=60)
    kind = models.CharField(max_length=20, choices=Kind.choices, default=Kind.BUILDER)
    mode = models.CharField(max_length=20, default="untimed")
    picker = models.CharField(max_length=32)
    spec = models.JSONField(default=dict)
    time_limit_seconds = models.IntegerField(null=True, blank=True)
    scoring_profile = models.CharField(max_length=20, default="practice")
    pattern = models.ForeignKey(
        PatternProfile, null=True, blank=True, on_delete=models.SET_NULL, related_name="presets"
    )
    use_count = models.IntegerField(default=0)
    last_used_at = models.DateTimeField(null=True, blank=True)
    sort_order = models.SmallIntegerField(default=0)
    client_id = models.UUIDField(null=True, blank=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "mcqbank_testpreset"
        ordering = ["sort_order", "-last_used_at"]
        indexes = [
            models.Index(fields=["user_id", "-last_used_at"], name="mcqpreset_usr_used_idx"),
            models.Index(fields=["scope_key", "sort_order"], name="mcqpreset_sys_order_idx"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["user_id", "client_id"],
                condition=Q(client_id__isnull=False),
                name="mcqpreset_unique_client_id",
            )
        ]

    def __str__(self) -> str:
        return f"{self.name} ({'system' if self.is_system else 'user'})"


class ExternalLog(UUIDModel):
    """Self-reported score for a link-out external set."""

    user_id = models.UUIDField(db_index=True)
    set = models.ForeignKey(McqSet, on_delete=models.PROTECT, related_name="external_logs")
    client_id = models.UUIDField()
    taken_on = models.DateField()
    score = models.DecimalField(max_digits=7, decimal_places=2)
    max_score = models.DecimalField(max_digits=7, decimal_places=2)
    score_pct = models.DecimalField(max_digits=5, decimal_places=1)
    chapter_id = models.UUIDField(null=True, blank=True)
    subject_id = models.UUIDField(null=True, blank=True)
    coverage_client_id = models.UUIDField()
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "mcqbank_externallog"
        ordering = ["-taken_on", "-created_at"]
        indexes = [
            models.Index(fields=["user_id", "-taken_on"], name="mcqextlog_usr_date_idx"),
            models.Index(fields=["set"], name="mcqextlog_set_idx"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["user_id", "client_id"],
                name="mcqextlog_unique_client_id",
            ),
            models.UniqueConstraint(
                fields=["user_id", "set", "taken_on"],
                condition=Q(deleted_at__isnull=True),
                name="mcqextlog_unique_user_set_day",
            ),
            models.CheckConstraint(
                condition=Q(score__gte=0) & Q(score__lte=models.F("max_score")),
                name="mcqextlog_score_range",
            ),
        ]

    def __str__(self) -> str:
        return f"Log {self.user_id} - {self.score}/{self.max_score}"


class RefSource(UUIDModel):
    """Prefix-to-link mapping for reference chips (e.g. bare acts, standards)."""

    prefix = models.CharField(max_length=32, unique=True)
    label = models.CharField(max_length=120)
    url_kind = models.CharField(max_length=20, default="bare_act")
    url_template = models.CharField(max_length=255, blank=True, default="")
    status = models.CharField(max_length=16, default="draft")
    verified_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True, default="")

    class Meta:
        db_table = "mcqbank_refsource"
        ordering = ["prefix"]

    def __str__(self) -> str:
        return f"{self.prefix}: {self.label}"


class AdaptiveRun(UUIDModel):
    """State for an adaptive practice run chaining 5-question rounds."""

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        STOPPED = "stopped", "Stopped"
        EXHAUSTED = "exhausted", "Exhausted"

    user_id = models.UUIDField(db_index=True)
    client_id = models.UUIDField()
    scope_type = models.CharField(max_length=16)  # 'chapter' | 'subject'
    scope_id = models.UUIDField()
    subject_key = models.CharField(max_length=80)
    chapter_key = models.CharField(max_length=80, blank=True, default="")
    target_p = models.DecimalField(max_digits=3, decimal_places=2, default=Decimal("0.70"))
    round_size = models.SmallIntegerField(default=5)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.ACTIVE)
    rounds_started = models.SmallIntegerField(default=0)
    rounds_applied = models.SmallIntegerField(default=0)
    last_active_at = models.DateTimeField(default=timezone.now)
    rev = models.IntegerField(default=0)

    class Meta:
        db_table = "mcqbank_adaptiverun"
        ordering = ["-last_active_at"]
        indexes = [
            models.Index(fields=["user_id", "status", "-last_active_at"], name="mcqrun_usr_st_act_idx"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["user_id", "scope_type", "scope_id"],
                condition=Q(status="active"),
                name="mcqrun_unique_active_scope",
            )
        ]

    def __str__(self) -> str:
        return f"AdaptiveRun {self.user_id} ({self.scope_type} {self.scope_id})"


class AdaptiveRound(UUIDModel):
    """One 5-question round within an adaptive run."""

    run = models.ForeignKey(AdaptiveRun, on_delete=models.CASCADE, related_name="rounds")
    round_no = models.SmallIntegerField()
    session_id = models.UUIDField()  # practice_session.id by value
    state = models.CharField(max_length=16, default="open")  # open, applied
    theta_before = models.DecimalField(max_digits=6, decimal_places=3, default=Decimal("0.000"))
    theta_after = models.DecimalField(max_digits=6, decimal_places=3, default=Decimal("0.000"))
    answered = models.SmallIntegerField(default=0)
    correct = models.SmallIntegerField(default=0)
    applied_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "mcqbank_adaptiveround"
        ordering = ["run", "round_no"]
        constraints = [
            models.UniqueConstraint(fields=["run", "round_no"], name="mcqround_unique_run_round"),
        ]

    def __str__(self) -> str:
        return f"Round {self.round_no} of run {self.run_id}"


class AbilityEstimate(UUIDModel):
    """Current Elo-style ability (theta in logits) of a student for a chapter or subject."""

    user_id = models.UUIDField(db_index=True)
    scope_type = models.CharField(max_length=16)  # 'chapter' | 'subject'
    scope_id = models.UUIDField()
    theta = models.DecimalField(max_digits=6, decimal_places=3, default=Decimal("0.000"))
    n = models.IntegerField(default=0)

    class Meta:
        db_table = "mcqbank_abilityestimate"
        constraints = [
            models.UniqueConstraint(fields=["user_id", "scope_type", "scope_id"], name="mcqability_unique_user_scope"),
        ]

    def __str__(self) -> str:
        return f"Ability {self.user_id} {self.scope_type}:{self.scope_id} = {self.theta}"
