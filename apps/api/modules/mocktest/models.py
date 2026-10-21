"""
Django models for F-08 Mock Tests and MTP.
"""

from __future__ import annotations

import base64
import uuid
from decimal import Decimal
from django.db import models
from django.utils import timezone


def generate_public_id() -> str:
    """Generate 8-character base32 public ID."""
    raw = uuid.uuid4().bytes[:5]
    return base64.b32encode(raw).decode("ascii").rstrip("=").lower()


class Series(models.Model):
    class Kind(models.TextChoices):
        INSTITUTE_MTP = "institute_mtp", "Institute MTP"
        INSTITUTE_RTP = "institute_rtp", "Institute RTP"
        INSTITUTE_OTHER = "institute_other", "Institute Other"
        COACHING = "coaching", "Coaching"
        PLATFORM = "platform", "Platform"
        PERSONAL = "personal", "Personal"

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        LIVE = "live", "Live"
        ARCHIVED = "archived", "Archived"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    course = models.ForeignKey("syllabus.Course", on_delete=models.RESTRICT, related_name="mock_series")
    level = models.ForeignKey("syllabus.Level", on_delete=models.RESTRICT, related_name="mock_series")
    kind = models.CharField(max_length=32, choices=Kind.choices, default=Kind.INSTITUTE_MTP)
    title = models.CharField(max_length=255)
    slug = models.SlugField(max_length=120)
    series_no = models.SmallIntegerField(null=True, blank=True)
    exam_term = models.ForeignKey("syllabus.ExamTerm", on_delete=models.SET_NULL, null=True, blank=True, related_name="mock_series")
    scheme = models.ForeignKey("syllabus.Scheme", on_delete=models.SET_NULL, null=True, blank=True, related_name="mock_series")
    issuer = models.CharField(max_length=120, blank=True, default="")
    release_schedule = models.JSONField(default=list, blank=True)
    source_url = models.URLField(max_length=500, null=True, blank=True)
    provenance_item_id = models.UUIDField(null=True, blank=True)
    owner_user_id = models.UUIDField(null=True, blank=True, db_index=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "mocktest_series"
        constraints = [
            models.UniqueConstraint(fields=["level", "slug"], name="uniq_mocktest_series_level_slug"),
        ]
        indexes = [
            models.Index(fields=["level", "status", "exam_term"], name="idx_mocktest_series_filter"),
        ]

    def __str__(self) -> str:
        return self.title


class Paper(models.Model):
    class Kind(models.TextChoices):
        MTP = "mtp", "MTP"
        RTP = "rtp", "RTP"
        SAMPLE = "sample", "Sample"
        MOCK = "mock", "Mock"
        GENERATED = "generated", "Generated"
        USER_UPLOAD = "user_upload", "User Upload"

    class SourceTag(models.TextChoices):
        INSTITUTE = "institute", "Institute"
        COURSE_BOUGHT = "course_bought", "Course Bought"
        USER = "user", "User"
        PLATFORM = "platform", "Platform"

    class Ownership(models.TextChoices):
        PLATFORM = "platform", "Platform"
        USER_UPLOADED = "user_uploaded", "User Uploaded"
        USER_CREATED = "user_created", "User Created"

    class RightsStatus(models.TextChoices):
        ORIGINAL = "original", "Original"
        LICENSED = "licensed", "Licensed"
        INSTITUTE_MATERIAL = "institute_material", "Institute Material"
        FAIR_DEALING = "fair_dealing", "Fair Dealing"
        TAKEDOWN = "takedown", "Takedown"

    class Visibility(models.TextChoices):
        PRIVATE = "private", "Private"
        LINK = "link", "Link"
        PUBLIC = "public", "Public"

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        IN_REVIEW = "in_review", "In Review"
        LIVE = "live", "Live"
        ARCHIVED = "archived", "Archived"
        TAKEN_DOWN = "taken_down", "Taken Down"

    class DeliveryMode(models.TextChoices):
        NATIVE = "native", "Native"
        PDF_COMPANION = "pdf_companion", "PDF Companion"

    class RevisionLabel(models.TextChoices):
        ORIGINAL = "original", "Original"
        REVISED = "revised", "Revised"
        SUPPLEMENTARY = "supplementary", "Supplementary"

    class AnswerKeyStatus(models.TextChoices):
        NONE = "none", "None"
        PARTIAL = "partial", "Partial"
        COMPLETE = "complete", "Complete"

    class SyllabusStatus(models.TextChoices):
        CURRENT = "current", "Current"
        OLD_SCHEME = "old_scheme", "Old Scheme"
        AMENDED = "amended", "Amended"
        UNKNOWN = "unknown", "Unknown"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    public_id = models.CharField(max_length=12, unique=True, default=generate_public_id, editable=False)
    series = models.ForeignKey(Series, on_delete=models.SET_NULL, null=True, blank=True, related_name="papers")
    course = models.ForeignKey("syllabus.Course", on_delete=models.RESTRICT, related_name="mock_papers")
    level = models.ForeignKey("syllabus.Level", on_delete=models.RESTRICT, related_name="mock_papers")
    scheme = models.ForeignKey("syllabus.Scheme", on_delete=models.RESTRICT, related_name="mock_papers")
    subject = models.ForeignKey("syllabus.Subject", on_delete=models.SET_NULL, null=True, blank=True, related_name="mock_papers")
    subject_key = models.CharField(max_length=64, null=True, blank=True)
    exam_term = models.ForeignKey("syllabus.ExamTerm", on_delete=models.SET_NULL, null=True, blank=True, related_name="mock_papers")
    title = models.CharField(max_length=255)
    slug = models.SlugField(max_length=120)
    description = models.TextField(max_length=500, blank=True, default="")
    kind = models.CharField(max_length=32, choices=Kind.choices, default=Kind.MTP)
    source_tag = models.CharField(max_length=32, choices=SourceTag.choices, default=SourceTag.INSTITUTE)
    coaching_name = models.CharField(max_length=120, blank=True, default="")
    ownership = models.CharField(max_length=32, choices=Ownership.choices, default=Ownership.PLATFORM)
    rights_status = models.CharField(max_length=32, choices=RightsStatus.choices, default=RightsStatus.ORIGINAL)
    visibility = models.CharField(max_length=20, choices=Visibility.choices, default=Visibility.PRIVATE)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    delivery_mode = models.CharField(max_length=20, choices=DeliveryMode.choices, default=DeliveryMode.NATIVE)
    source_pdf_url = models.URLField(max_length=500, blank=True, default="")
    solution_pdf_url = models.URLField(max_length=500, blank=True, default="")
    revision_label = models.CharField(max_length=20, choices=RevisionLabel.choices, default=RevisionLabel.ORIGINAL)
    revision_of = models.ForeignKey("self", on_delete=models.SET_NULL, null=True, blank=True, related_name="revisions")
    released_at = models.DateTimeField(null=True, blank=True)
    answer_key_status = models.CharField(max_length=20, choices=AnswerKeyStatus.choices, default=AnswerKeyStatus.NONE)
    key_released_at = models.DateTimeField(null=True, blank=True)
    syllabus_status = models.CharField(max_length=20, choices=SyllabusStatus.choices, default=SyllabusStatus.UNKNOWN)
    live_version_id = models.UUIDField(null=True, blank=True)
    owner_user_id = models.UUIDField(null=True, blank=True, db_index=True)
    client_id = models.UUIDField(null=True, blank=True)
    origin_module = models.CharField(max_length=32, default="editor")
    external_ref = models.CharField(max_length=120, null=True, blank=True)
    provenance_item_id = models.UUIDField(null=True, blank=True)
    provenance_version_id = models.UUIDField(null=True, blank=True)
    entitlement_key = models.CharField(max_length=120, null=True, blank=True)
    needs_attention = models.BooleanField(default=False)
    attempt_count = models.IntegerField(default=0)
    deleted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "mocktest_paper"
        indexes = [
            models.Index(fields=["level", "scheme", "status", "-released_at"], name="idx_mocktest_paper_cat"),
            models.Index(fields=["series", "subject_key"], name="idx_mocktest_paper_series"),
            models.Index(fields=["owner_user_id", "status", "-updated_at"], name="idx_mocktest_paper_owner"),
        ]

    def __str__(self) -> str:
        return self.title


class PaperVersion(models.Model):
    class State(models.TextChoices):
        DRAFT = "draft", "Draft"
        IN_REVIEW = "in_review", "In Review"
        LIVE = "live", "Live"
        SUPERSEDED = "superseded", "Superseded"
        REJECTED = "rejected", "Rejected"
        WITHDRAWN = "withdrawn", "Withdrawn"

    class SectionTiming(models.TextChoices):
        NONE = "none", "None"
        SEQUENTIAL = "sequential", "Sequential"

    class ScoringMode(models.TextChoices):
        RULE = "rule", "Rule"
        EXPLICIT = "explicit", "Explicit"

    class FocusPolicy(models.TextChoices):
        OFF = "off", "Off"
        LOG = "log", "Log"

    class Calculator(models.TextChoices):
        NONE = "none", "None"
        BASIC = "basic", "Basic"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    paper = models.ForeignKey(Paper, on_delete=models.CASCADE, related_name="versions")
    version_no = models.IntegerField(default=1)
    state = models.CharField(max_length=20, choices=State.choices, default=State.DRAFT)
    blueprint_schema = models.SmallIntegerField(default=1)
    total_marks = models.DecimalField(max_digits=7, decimal_places=2, default=Decimal("100.00"))
    duration_seconds = models.IntegerField(default=10800)  # 3 hours
    reading_seconds = models.IntegerField(default=0)
    upload_window_seconds = models.IntegerField(default=0)
    section_timing = models.CharField(max_length=20, choices=SectionTiming.choices, default=SectionTiming.NONE)
    scoring_mode = models.CharField(max_length=20, choices=ScoringMode.choices, default=ScoringMode.RULE)
    negative_mode = models.CharField(max_length=20, null=True, blank=True)
    negative_value = models.DecimalField(max_digits=5, decimal_places=3, null=True, blank=True)
    negative_source_note = models.TextField(blank=True, default="")
    negative_verified = models.BooleanField(default=False)
    instructions_md = models.TextField(max_length=6000, blank=True, default="")
    allowed_run_modes = models.JSONField(default=list, blank=True)  # ["exam", "relaxed"]
    relaxed_max_pauses = models.SmallIntegerField(default=3)
    relaxed_max_pause_seconds = models.IntegerField(default=1800)
    focus_policy = models.CharField(max_length=20, choices=FocusPolicy.choices, default=FocusPolicy.LOG)
    shuffle_questions = models.BooleanField(default=False)
    shuffle_options = models.BooleanField(default=False)
    calculator = models.CharField(max_length=20, choices=Calculator.choices, default=Calculator.NONE)
    languages = models.JSONField(default=list, blank=True)  # ["en"]
    item_count = models.SmallIntegerField(default=0)
    content_hash = models.CharField(max_length=64, null=True, blank=True, db_index=True)
    generation_spec = models.JSONField(null=True, blank=True)
    created_by = models.UUIDField(null=True, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "mocktest_paperversion"
        constraints = [
            models.UniqueConstraint(fields=["paper", "version_no"], name="uniq_mocktest_paper_version_no"),
        ]

    def __str__(self) -> str:
        return f"{self.paper.title} v{self.version_no}"


class Section(models.Model):
    class Kind(models.TextChoices):
        OBJECTIVE = "objective", "Objective"
        DESCRIPTIVE = "descriptive", "Descriptive"
        MIXED = "mixed", "Mixed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    version = models.ForeignKey(PaperVersion, on_delete=models.CASCADE, related_name="sections")
    key = models.CharField(max_length=16)  # e.g. "A", "B"
    title = models.CharField(max_length=255)
    position = models.SmallIntegerField(default=1)
    kind = models.CharField(max_length=20, choices=Kind.choices, default=Kind.OBJECTIVE)
    duration_seconds = models.IntegerField(null=True, blank=True)
    instructions_md = models.TextField(blank=True, default="")
    marks_total = models.DecimalField(max_digits=7, decimal_places=2, default=Decimal("0.00"))

    class Meta:
        db_table = "mocktest_section"
        constraints = [
            models.UniqueConstraint(fields=["version", "key"], name="uniq_mocktest_section_version_key"),
        ]
        ordering = ["position"]

    def __str__(self) -> str:
        return f"{self.key}: {self.title}"


class ChoiceGroup(models.Model):
    class OverflowPolicy(models.TextChoices):
        BLOCK = "block", "Block"
        FIRST_N = "first_n", "First N"
        BEST_N = "best_n", "Best N"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    section = models.ForeignKey(Section, on_delete=models.CASCADE, related_name="choice_groups")
    key = models.CharField(max_length=32)
    label = models.CharField(max_length=255)  # e.g. "Answer any 4 of 6"
    required_count = models.SmallIntegerField(default=1)
    overflow_policy = models.CharField(max_length=20, choices=OverflowPolicy.choices, default=OverflowPolicy.BLOCK)
    position = models.SmallIntegerField(default=1)

    class Meta:
        db_table = "mocktest_choicegroup"
        constraints = [
            models.UniqueConstraint(fields=["section", "key"], name="uniq_mocktest_choicegroup_section_key"),
        ]

    def __str__(self) -> str:
        return self.label


class Item(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    version = models.ForeignKey(PaperVersion, on_delete=models.CASCADE, related_name="items")
    section = models.ForeignKey(Section, on_delete=models.CASCADE, related_name="items")
    choice_group = models.ForeignKey(ChoiceGroup, on_delete=models.SET_NULL, null=True, blank=True, related_name="items")
    position = models.SmallIntegerField()  # 1-based order
    display_label = models.CharField(max_length=32)  # "Q.1", "Q.4(b)"
    question = models.ForeignKey("questionbank.Question", on_delete=models.RESTRICT, related_name="mock_items")
    question_version_id = models.UUIDField(null=True, blank=True)
    marks = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal("1.00"))
    negative_marks = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    suggested_seconds = models.IntegerField(null=True, blank=True)

    class Meta:
        db_table = "mocktest_item"
        constraints = [
            models.UniqueConstraint(fields=["version", "position"], name="uniq_mocktest_item_version_pos"),
        ]
        indexes = [
            models.Index(fields=["question"], name="idx_mocktest_item_q"),
            models.Index(fields=["section", "position"], name="idx_mocktest_item_sec_pos"),
        ]
        ordering = ["position"]

    def __str__(self) -> str:
        return f"{self.display_label} ({self.marks} marks)"


class ExamFormat(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        ACTIVE = "active", "Active"
        RETIRED = "retired", "Retired"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    course = models.ForeignKey("syllabus.Course", on_delete=models.RESTRICT, related_name="exam_formats")
    level = models.ForeignKey("syllabus.Level", on_delete=models.RESTRICT, related_name="exam_formats")
    subject_key = models.CharField(max_length=64, null=True, blank=True)
    name = models.CharField(max_length=255)
    effective_from = models.DateField(default=timezone.now)
    effective_to = models.DateField(null=True, blank=True)
    total_marks = models.DecimalField(max_digits=7, decimal_places=2, default=Decimal("100.00"))
    duration_seconds = models.IntegerField(default=10800)
    reading_seconds = models.IntegerField(default=0)
    sections_spec = models.JSONField(default=dict)
    minutes_per_mark = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)
    scoring_rule_ref = models.UUIDField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    verified = models.BooleanField(default=False)
    source_note = models.TextField(blank=True, default="")
    source_url = models.URLField(max_length=500, null=True, blank=True)
    verified_by = models.UUIDField(null=True, blank=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "mocktest_examformat"

    def __str__(self) -> str:
        return self.name


class PaperReview(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        CLAIMED = "claimed", "Claimed"
        APPROVED = "approved", "Approved"
        CHANGES_REQUESTED = "changes_requested", "Changes Requested"
        REJECTED = "rejected", "Rejected"
        WITHDRAWN = "withdrawn", "Withdrawn"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    paper_version = models.ForeignKey(PaperVersion, on_delete=models.CASCADE, related_name="reviews")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    item_review_ids = models.JSONField(default=list, blank=True)
    auto_checks = models.JSONField(default=dict, blank=True)
    reviewer_id = models.UUIDField(null=True, blank=True)
    decision_code = models.CharField(max_length=32, null=True, blank=True)
    note = models.TextField(blank=True, default="")
    submitted_at = models.DateTimeField(default=timezone.now)
    decided_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "mocktest_paperreview"
        indexes = [
            models.Index(fields=["status", "submitted_at"], name="idx_mocktest_review_status"),
        ]


class Attempt(models.Model):
    class RunMode(models.TextChoices):
        EXAM = "exam", "Exam"
        RELAXED = "relaxed", "Relaxed"

    class Phase(models.TextChoices):
        INSTRUCTIONS = "instructions", "Instructions"
        READING = "reading", "Reading"
        WRITING = "writing", "Writing"
        UPLOAD = "upload", "Upload"
        DONE = "done", "Done"
        ABANDONED = "abandoned", "Abandoned"

    class Completion(models.TextChoices):
        SUBMITTED = "submitted", "Submitted"
        AUTO_SUBMITTED = "auto_submitted", "Auto Submitted"
        ABANDONED_PARTIAL = "abandoned_partial", "Abandoned Partial"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user_id = models.UUIDField(db_index=True)
    client_id = models.UUIDField()
    session_id = models.UUIDField(unique=True)
    paper = models.ForeignKey(Paper, on_delete=models.RESTRICT, related_name="attempts")
    paper_version = models.ForeignKey(PaperVersion, on_delete=models.RESTRICT, related_name="attempts")
    attempt_no = models.SmallIntegerField(default=1)
    run_mode = models.CharField(max_length=20, choices=RunMode.choices, default=RunMode.EXAM)
    section_scope = models.CharField(max_length=16, null=True, blank=True)
    delivery_mode = models.CharField(max_length=20, default="native")
    phase = models.CharField(max_length=20, choices=Phase.choices, default=Phase.INSTRUCTIONS)
    instructions_accepted_at = models.DateTimeField(null=True, blank=True)
    reading_started_at = models.DateTimeField(null=True, blank=True)
    reading_ends_at = models.DateTimeField(null=True, blank=True)
    writing_started_at = models.DateTimeField(null=True, blank=True)
    writing_ends_at = models.DateTimeField(null=True, blank=True)
    upload_until = models.DateTimeField(null=True, blank=True)
    extra_seconds = models.IntegerField(default=0)
    time_extension_pct = models.SmallIntegerField(default=0)
    pause_count = models.SmallIntegerField(default=0)
    paused_seconds = models.IntegerField(default=0)
    lease_epoch = models.IntegerField(default=0)
    lease_tab_id = models.CharField(max_length=64, null=True, blank=True)
    lease_label = models.CharField(max_length=120, blank=True, default="")
    lease_expires_at = models.DateTimeField(null=True, blank=True)
    last_position = models.SmallIntegerField(null=True, blank=True)
    last_section_key = models.CharField(max_length=16, null=True, blank=True)
    last_heartbeat_at = models.DateTimeField(null=True, blank=True)
    layout = models.JSONField(default=list, blank=True)
    choice_resolution = models.JSONField(default=dict, blank=True)
    focus_lost_count = models.IntegerField(default=0)
    focus_lost_seconds = models.IntegerField(default=0)
    offline_seconds = models.IntegerField(default=0)
    fullscreen_exit_count = models.SmallIntegerField(default=0)
    max_write_lag_ms = models.IntegerField(default=0)
    replay_flagged = models.BooleanField(default=False)
    integrity_class = models.CharField(max_length=32, null=True, blank=True)
    completion = models.CharField(max_length=20, choices=Completion.choices, null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    time_used_seconds = models.IntegerField(null=True, blank=True)
    score = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True)
    max_score = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True)
    percent = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    comparable_score = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True)
    comparable_max = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True)
    score_status = models.CharField(max_length=20, null=True, blank=True)
    percentile_eligible = models.BooleanField(default=False)
    share_anonymous = models.BooleanField(default=False)
    rev = models.IntegerField(default=0)
    deleted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "mocktest_attempt"
        constraints = [
            models.UniqueConstraint(fields=["user_id", "client_id"], name="uniq_mocktest_attempt_user_client"),
            # Exclusivity: one live strict exam per student
            models.UniqueConstraint(
                fields=["user_id"],
                condition=models.Q(run_mode="exam", phase__in=["reading", "writing", "upload"], deleted_at__isnull=True),
                name="uniq_mocktest_attempt_live_exam",
            ),
            # Exclusivity: one open attempt per paper per student
            models.UniqueConstraint(
                fields=["user_id", "paper"],
                condition=models.Q(phase__in=["instructions", "reading", "writing", "upload"], section_scope__isnull=True, deleted_at__isnull=True),
                name="uniq_mocktest_attempt_open_paper",
            ),
        ]
        indexes = [
            models.Index(fields=["user_id", "-completed_at"], name="idx_mocktest_attempt_history"),
            models.Index(fields=["user_id", "paper", "attempt_no"], name="idx_mocktest_attempt_compare"),
            models.Index(fields=["paper_version", "percent"], name="idx_mocktest_attempt_cohort"),
            models.Index(fields=["phase", "writing_ends_at"], name="idx_mocktest_attempt_sweep"),
        ]

    def __str__(self) -> str:
        return f"Attempt {self.attempt_no} on {self.paper.title} ({self.phase})"


class AttemptSection(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        OPEN = "open", "Open"
        CLOSED = "closed", "Closed"

    attempt = models.ForeignKey(Attempt, on_delete=models.CASCADE, related_name="sections")
    section = models.ForeignKey(Section, on_delete=models.CASCADE, related_name="attempt_sections")
    position = models.SmallIntegerField(default=1)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    opens_at = models.DateTimeField(null=True, blank=True)
    closes_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    closed_by = models.CharField(max_length=20, null=True, blank=True)
    score = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True)
    max_score = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True)
    answered = models.SmallIntegerField(default=0)
    correct = models.SmallIntegerField(default=0)
    incorrect = models.SmallIntegerField(default=0)
    skipped = models.SmallIntegerField(default=0)
    not_counted = models.SmallIntegerField(default=0)
    time_spent_seconds = models.IntegerField(default=0)

    class Meta:
        db_table = "mocktest_attemptsection"
        constraints = [
            models.UniqueConstraint(fields=["attempt", "section"], name="uniq_mocktest_attemptsec_att_sec"),
        ]
        ordering = ["position"]


class AttemptEvent(models.Model):
    id = models.BigAutoField(primary_key=True)
    attempt = models.ForeignKey(Attempt, on_delete=models.CASCADE, related_name="events")
    user_id = models.UUIDField(db_index=True)
    type = models.CharField(max_length=32)
    client_ts = models.DateTimeField(null=True, blank=True)
    server_ts = models.DateTimeField(default=timezone.now)
    duration_ms = models.IntegerField(null=True, blank=True)
    position = models.SmallIntegerField(null=True, blank=True)
    meta = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "mocktest_attemptevent"
        indexes = [
            models.Index(fields=["attempt", "server_ts"], name="idx_mocktest_event_att_time"),
        ]


class CohortStat(models.Model):
    paper_version = models.OneToOneField(PaperVersion, on_delete=models.CASCADE, primary_key=True, related_name="cohort_stat")
    n = models.IntegerField(default=0)
    histogram = models.JSONField(default=dict, blank=True)
    quantiles = models.JSONField(default=dict, blank=True)
    mean = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    stddev = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    published = models.BooleanField(default=False)
    floor = models.SmallIntegerField(default=30)
    computed_at = models.DateTimeField(default=timezone.now)
    last_new_count = models.IntegerField(default=0)

    class Meta:
        db_table = "mocktest_cohortstat"


class Settings(models.Model):
    user_id = models.UUIDField(primary_key=True)
    time_extension_pct = models.SmallIntegerField(default=0)
    default_run_mode = models.CharField(max_length=20, default="relaxed")
    focus_reminders = models.BooleanField(default=False)
    keyboard_shortcuts = models.BooleanField(default=True)
    text_size = models.SmallIntegerField(default=0)
    percentile_optin = models.BooleanField(null=True, blank=True)
    percentile_consent_at = models.DateTimeField(null=True, blank=True)
    percentile_consent_version = models.CharField(max_length=32, null=True, blank=True)
    tz = models.CharField(max_length=64, default="Asia/Kolkata")
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "mocktest_settings"


class AuditLog(models.Model):
    id = models.BigAutoField(primary_key=True)
    actor_id = models.UUIDField(null=True, blank=True)
    action = models.CharField(max_length=64)
    target_type = models.CharField(max_length=32)
    target_id = models.UUIDField(null=True, blank=True)
    meta = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "mocktest_auditlog"
        indexes = [
            models.Index(fields=["target_type", "target_id", "-created_at"], name="idx_mocktest_audit_target"),
        ]
