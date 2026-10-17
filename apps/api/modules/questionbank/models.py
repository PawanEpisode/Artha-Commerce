from __future__ import annotations

import secrets
from decimal import Decimal

from django.contrib.postgres.search import SearchVectorField
from django.db import models
from django.db.models import Q
from django.utils import timezone

from core.models import TimeStampedModel, UUIDModel

CROCKFORD_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


def generate_public_id(length: int = 10) -> str:
    """Generate a Crockford Base32 10-character string (excludes I, L, O, U)."""
    return "".join(secrets.choice(CROCKFORD_ALPHABET) for _ in range(length))


class Question(UUIDModel):
    class Kind(models.TextChoices):
        MCQ_SINGLE = "mcq_single", "Single-choice MCQ"
        MCQ_MULTI = "mcq_multi", "Multi-choice MCQ"
        TRUE_FALSE = "true_false", "True / False"
        NUMERIC = "numeric", "Numeric answer"
        CASE_STUDY = "case_study", "Case study parent"
        LONG_FORM = "long_form", "Long-form descriptive"
        PRACTICAL = "practical", "Practical problem"

    class Ownership(models.TextChoices):
        PLATFORM = "platform", "Platform created"
        USER_UPLOADED = "user_uploaded", "User uploaded"
        USER_CREATED = "user_created", "User created"

    class RightsStatus(models.TextChoices):
        ORIGINAL = "original", "Original"
        LICENSED = "licensed", "Licensed"
        INSTITUTE_MATERIAL = "institute_material", "Institute material"
        THIRD_PARTY_CLAIMED = "third_party_claimed", "Third party claimed"
        UNKNOWN = "unknown", "Unknown"

    class Visibility(models.TextChoices):
        PRIVATE = "private", "Private"
        LINK = "link", "Shared via link"
        PUBLIC = "public", "Public"

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        ARCHIVED = "archived", "Archived"
        TAKEN_DOWN = "taken_down", "Taken down"
        MERGED = "merged", "Merged"

    class SourceKind(models.TextChoices):
        INSTITUTE_MAT = "institute_mat", "Study Material"
        INSTITUTE_PYQ = "institute_pyq", "Previous Year Question"
        INSTITUTE_MTP = "institute_mtp", "Mock Test Paper"
        INSTITUTE_RTP = "institute_rtp", "Revision Test Paper"
        INSTITUTE_MCQ = "institute_mcq", "Institute MCQ booklet"
        COACHING = "coaching", "Coaching material"
        TEACHER_LIST = "teacher_list", "Teacher list"
        PLATFORM = "platform", "Artha Platform"
        USER = "user", "User contribution"

    class Bloom(models.TextChoices):
        REMEMBER = "remember", "Remember"
        UNDERSTAND = "understand", "Understand"
        APPLY = "apply", "Apply"
        ANALYSE = "analyse", "Analyse"
        EVALUATE = "evaluate", "Evaluate"
        CREATE = "create", "Create"

    class Nature(models.TextChoices):
        THEORY = "theory", "Theory"
        PRACTICAL = "practical", "Practical"
        FORMULA = "formula", "Formula"
        SECTION = "section", "Section"
        CASE_LAW = "case_law", "Case law"
        APPLICATION = "application", "Application"

    public_id = models.CharField(max_length=10, unique=True, default=generate_public_id, editable=False)
    kind = models.CharField(max_length=32, choices=Kind.choices)
    parent = models.ForeignKey("self", null=True, blank=True, on_delete=models.RESTRICT, related_name="children")
    position = models.SmallIntegerField(null=True, blank=True)
    ownership = models.CharField(max_length=32, choices=Ownership.choices, default=Ownership.PLATFORM)
    owner_user_id = models.UUIDField(null=True, blank=True, db_index=True)
    owner_anonymised = models.BooleanField(default=False)
    created_by = models.UUIDField(null=True, blank=True)
    rights_status = models.CharField(max_length=32, choices=RightsStatus.choices, default=RightsStatus.UNKNOWN)
    rights_note = models.TextField(blank=True, default="")
    visibility = models.CharField(max_length=16, choices=Visibility.choices, default=Visibility.PRIVATE)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.ACTIVE)
    needs_attention = models.BooleanField(default=False)
    merged_into = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.SET_NULL, related_name="merged_from"
    )
    live_version = models.ForeignKey(
        "QuestionVersion", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    current_version = models.ForeignKey(
        "QuestionVersion", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    # Denormalized taxonomy
    course = models.ForeignKey("syllabus.Course", null=True, blank=True, on_delete=models.RESTRICT, related_name="+")
    level = models.ForeignKey("syllabus.Level", null=True, blank=True, on_delete=models.RESTRICT, related_name="+")
    scheme = models.ForeignKey("syllabus.Scheme", null=True, blank=True, on_delete=models.RESTRICT, related_name="+")
    primary_subject = models.ForeignKey(
        "syllabus.Subject", null=True, blank=True, on_delete=models.RESTRICT, related_name="+"
    )
    primary_chapter = models.ForeignKey(
        "syllabus.Chapter", null=True, blank=True, on_delete=models.RESTRICT, related_name="+"
    )
    primary_topic = models.ForeignKey(
        "syllabus.Topic", null=True, blank=True, on_delete=models.RESTRICT, related_name="+"
    )
    subject_key = models.CharField(max_length=80, blank=True, default="")
    chapter_key = models.CharField(max_length=100, blank=True, default="")

    # Source & metadata
    source_kind = models.CharField(max_length=32, choices=SourceKind.choices, default=SourceKind.PLATFORM)
    source_name = models.CharField(max_length=120, blank=True, default="")
    source_url = models.URLField(blank=True, default="")
    source_ref = models.CharField(max_length=200, blank=True, default="")
    source_year = models.SmallIntegerField(null=True, blank=True)
    source_term_code = models.CharField(max_length=16, blank=True, default="")
    exam_term = models.ForeignKey(
        "syllabus.ExamTerm", null=True, blank=True, on_delete=models.RESTRICT, related_name="+"
    )
    difficulty = models.SmallIntegerField(null=True, blank=True)
    bloom = models.CharField(max_length=16, blank=True, default="")
    nature = models.CharField(max_length=32, blank=True, default="")
    marks = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True)

    # Search & tags
    tag_slugs = models.JSONField(default=list, blank=True)
    search_keys = models.JSONField(default=list, blank=True)
    stem_head = models.CharField(max_length=300, blank=True, default="")
    search_text = models.TextField(blank=True, default="")
    search_tsv = SearchVectorField(null=True, blank=True, editable=False)
    seo_indexable = models.BooleanField(default=False)

    # Origin & provenance
    origin_module = models.CharField(max_length=32, default="editor")
    external_ref = models.CharField(max_length=200, null=True, blank=True)  # noqa: DJ001
    provenance_item_id = models.UUIDField(null=True, blank=True)
    provenance_version_id = models.UUIDField(null=True, blank=True)
    is_verified = models.BooleanField(default=False)
    client_id = models.UUIDField(null=True, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    def save(self, *args, **kwargs):
        """
        `marks` is a copy of the marks of the version a student sees (the live version, or the current draft before
        anything is live). The question list reads this copy and the detail page reads the version, so every save brings
        the copy back in line: the two can never show different numbers.
        """
        version_id = self.live_version_id or self.current_version_id
        if version_id:
            version = self.live_version if self.live_version_id else self.current_version
            if version is not None and self.marks != version.marks:
                self.marks = version.marks
                fields = kwargs.get("update_fields")
                if fields is not None:
                    kwargs["update_fields"] = {*fields, "marks"}
        super().save(*args, **kwargs)

    class Meta:
        db_table = "questionbank_question"
        constraints = [
            models.UniqueConstraint(
                fields=["origin_module", "external_ref"],
                condition=Q(external_ref__isnull=False),
                name="qb_q_origin_ext_ref_unique",
            ),
            models.UniqueConstraint(
                fields=["owner_user_id", "client_id"],
                condition=Q(client_id__isnull=False),
                name="qb_q_owner_client_unique",
            ),
            models.CheckConstraint(
                condition=Q(parent__isnull=True) | ~Q(parent=models.F("id")),
                name="qb_q_parent_not_self",
            ),
            models.CheckConstraint(
                condition=Q(source_year__isnull=True) | (Q(source_year__gte=1990) & Q(source_year__lte=2100)),
                name="qb_q_source_year_range",
            ),
            models.CheckConstraint(
                condition=Q(difficulty__isnull=True) | (Q(difficulty__gte=1) & Q(difficulty__lte=5)),
                name="qb_q_difficulty_range",
            ),
        ]
        indexes = [
            models.Index(fields=["primary_chapter", "published_at", "id"], name="qb_q_ch_pub_idx"),
            models.Index(fields=["primary_subject", "kind", "source_year", "id"], name="qb_q_subj_kind_yr_idx"),
            models.Index(fields=["course", "level", "kind", "id"], name="qb_q_course_lvl_kind_idx"),
            models.Index(fields=["owner_user_id", "status", "updated_at"], name="qb_q_owner_status_idx"),
            models.Index(fields=["parent", "position"], name="qb_q_parent_pos_idx"),
            models.Index(fields=["source_kind", "source_year", "source_term_code"], name="qb_q_source_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.public_id} ({self.kind})"


class QuestionVersion(UUIDModel):
    class State(models.TextChoices):
        DRAFT = "draft", "Draft"
        IN_REVIEW = "in_review", "In review"
        LIVE = "live", "Live"
        SUPERSEDED = "superseded", "Superseded"
        REJECTED = "rejected", "Rejected"
        WITHDRAWN = "withdrawn", "Withdrawn"

    class ChangeKind(models.TextChoices):
        CREATE = "create", "Create"
        EDIT = "edit", "Edit"
        TYPO = "typo", "Typo fix"
        KEY_FIX = "key_fix", "Key fix"
        REMAP = "remap", "Taxonomy remap"
        IMPORT_UPDATE = "import_update", "Import update"

    class MultiScoring(models.TextChoices):
        ALL_OR_NOTHING = "all_or_nothing", "All or nothing"
        PARTIAL_STRICT = "partial_strict", "Partial strict"
        PARTIAL_NET = "partial_net", "Partial net"

    question = models.ForeignKey(Question, on_delete=models.RESTRICT, related_name="versions")
    version_no = models.IntegerField()
    state = models.CharField(max_length=16, choices=State.choices, default=State.DRAFT)
    change_kind = models.CharField(max_length=32, choices=ChangeKind.choices, default=ChangeKind.CREATE)
    change_note = models.TextField(blank=True, default="")
    authored_by = models.UUIDField(null=True, blank=True)
    stem_md = models.TextField()
    stem_text = models.TextField(blank=True, default="")
    explanation_md = models.TextField(blank=True, default="")
    explanation_source = models.CharField(max_length=200, blank=True, default="")
    reference_labels = models.JSONField(default=list, blank=True)
    marks = models.DecimalField(max_digits=5, decimal_places=1, default=Decimal("1.0"))
    negative_marks = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)
    multi_scoring = models.CharField(max_length=20, choices=MultiScoring.choices, default=MultiScoring.ALL_OR_NOTHING)
    suggested_seconds = models.SmallIntegerField(null=True, blank=True)
    shuffle_options = models.BooleanField(default=True)
    lang = models.CharField(max_length=8, default="en")
    content_schema = models.SmallIntegerField(default=1)
    content_hash = models.CharField(max_length=64, db_index=True)

    submitted_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.UUIDField(null=True, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    live_at = models.DateTimeField(null=True, blank=True)
    superseded_at = models.DateTimeField(null=True, blank=True)

    def save(self, *args, **kwargs):
        """Editing a version's marks moves the question's copy too (see Question.save)."""
        super().save(*args, **kwargs)
        fields = kwargs.get("update_fields")
        if fields is None or "marks" in fields:
            Question.objects.filter(
                Q(live_version_id=self.pk) | Q(live_version__isnull=True, current_version_id=self.pk)
            ).exclude(marks=self.marks).update(marks=self.marks)

    class Meta:
        db_table = "questionbank_questionversion"
        constraints = [
            models.UniqueConstraint(fields=["question", "version_no"], name="qb_qv_q_ver_unique"),
            models.UniqueConstraint(
                fields=["question"],
                condition=Q(state="live"),
                name="qb_qv_one_live_unique",
            ),
            models.UniqueConstraint(
                fields=["question"],
                condition=Q(state="draft"),
                name="qb_qv_one_draft_unique",
            ),
            models.UniqueConstraint(
                fields=["question"],
                condition=Q(state="in_review"),
                name="qb_qv_one_in_review_unique",
            ),
            models.CheckConstraint(condition=Q(marks__gte=0), name="qb_qv_marks_gte_0"),
            models.CheckConstraint(
                condition=Q(negative_marks__isnull=True) | Q(negative_marks__gte=0),
                name="qb_qv_neg_marks_gte_0",
            ),
        ]
        indexes = [
            models.Index(fields=["question", "-version_no"], name="qb_qv_q_ver_desc_idx"),
            models.Index(fields=["content_hash"], name="qb_qv_content_hash_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.question.public_id} v{self.version_no} ({self.state})"


class Option(UUIDModel):
    version = models.ForeignKey(QuestionVersion, on_delete=models.CASCADE, related_name="options")
    position = models.SmallIntegerField()
    body_md = models.TextField()
    body_text = models.TextField(blank=True, default="")
    is_correct = models.BooleanField(default=False)
    feedback_md = models.TextField(blank=True, default="")
    pinned = models.BooleanField(default=False)

    class Meta:
        db_table = "questionbank_option"
        ordering = ["position"]
        constraints = [
            models.UniqueConstraint(fields=["version", "position"], name="qb_opt_version_pos_unique"),
        ]

    def __str__(self) -> str:
        return f"Option {self.position} of v{self.version_id}"


class AnswerKey(TimeStampedModel):
    version = models.OneToOneField(
        QuestionVersion, primary_key=True, on_delete=models.CASCADE, related_name="answer_key"
    )
    numeric_value = models.DecimalField(max_digits=24, decimal_places=6)
    tolerance_abs = models.DecimalField(max_digits=24, decimal_places=6, default=Decimal("0"))
    tolerance_rel = models.DecimalField(max_digits=7, decimal_places=4, default=Decimal("0"))
    accepted_values = models.JSONField(default=list, blank=True)
    unit = models.CharField(max_length=32, blank=True, default="")
    unit_required = models.BooleanField(default=False)
    key_note = models.TextField(blank=True, default="")

    class Meta:
        db_table = "questionbank_answerkey"

    def __str__(self) -> str:
        return f"AnswerKey for v{self.version_id}: {self.numeric_value}"


class Rubric(TimeStampedModel):
    class Source(models.TextChoices):
        INSTITUTE = "institute", "Institute solution"
        EDITOR = "editor", "Editor"
        CONTRIBUTOR = "contributor", "Contributor"
        AI_DRAFT = "ai_draft", "AI draft"

    version = models.OneToOneField(QuestionVersion, primary_key=True, on_delete=models.CASCADE, related_name="rubric")
    reference_solution_md = models.TextField()
    answer_template_md = models.TextField(blank=True, default="")
    total_marks = models.DecimalField(max_digits=5, decimal_places=1)
    suggested_words = models.SmallIntegerField(null=True, blank=True)
    keywords = models.JSONField(default=list, blank=True)
    common_mistakes_md = models.TextField(blank=True, default="")
    source = models.CharField(max_length=32, choices=Source.choices, default=Source.EDITOR)
    reviewed_by = models.UUIDField(null=True, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "questionbank_rubric"

    def __str__(self) -> str:
        return f"Rubric for v{self.version_id} ({self.total_marks} marks)"


class RubricStep(UUIDModel):
    class Kind(models.TextChoices):
        CONCEPT = "concept", "Concept"
        CALCULATION = "calculation", "Calculation"
        WORKING_NOTE = "working_note", "Working note"
        PRESENTATION = "presentation", "Presentation"
        CONCLUSION = "conclusion", "Conclusion"
        FORMAT = "format", "Format"

    rubric = models.ForeignKey(Rubric, on_delete=models.CASCADE, related_name="steps")
    position = models.SmallIntegerField()
    title = models.CharField(max_length=200)
    description_md = models.TextField(blank=True, default="")
    marks = models.DecimalField(max_digits=4, decimal_places=1)
    kind = models.CharField(max_length=32, choices=Kind.choices, default=Kind.CONCEPT)
    keywords = models.JSONField(default=list, blank=True)
    mandatory = models.BooleanField(default=False)
    partial_allowed = models.BooleanField(default=True)

    class Meta:
        db_table = "questionbank_rubricstep"
        ordering = ["position"]
        constraints = [
            models.UniqueConstraint(fields=["rubric", "position"], name="qb_rubricstep_pos_unique"),
        ]

    def __str__(self) -> str:
        return f"Step {self.position}: {self.title} ({self.marks}m)"


class QuestionTopic(UUIDModel):
    class Status(models.TextChoices):
        SUGGESTED = "suggested", "Suggested"
        CONFIRMED = "confirmed", "Confirmed"
        REJECTED = "rejected", "Rejected"

    class Origin(models.TextChoices):
        AUTHOR = "author", "Author"
        EDITOR = "editor", "Editor"
        AI = "ai", "AI mapping"
        INGESTION = "ingestion", "Ingestion pipeline"
        INHERITED = "inherited", "Inherited from case study parent"
        REMAP = "remap", "Scheme remap"

    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name="topics")
    chapter = models.ForeignKey("syllabus.Chapter", on_delete=models.RESTRICT, related_name="+")
    topic = models.ForeignKey("syllabus.Topic", null=True, blank=True, on_delete=models.RESTRICT, related_name="+")
    subject = models.ForeignKey("syllabus.Subject", on_delete=models.RESTRICT, related_name="+")
    scheme = models.ForeignKey("syllabus.Scheme", on_delete=models.RESTRICT, related_name="+")
    subject_key = models.CharField(max_length=80)
    chapter_key = models.CharField(max_length=100)
    is_primary = models.BooleanField(default=False)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.CONFIRMED)
    origin = models.CharField(max_length=32, choices=Origin.choices, default=Origin.EDITOR)
    confidence = models.DecimalField(max_digits=3, decimal_places=2, null=True, blank=True)
    decided_by = models.UUIDField(null=True, blank=True)
    decided_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "questionbank_questiontopic"
        constraints = [
            models.UniqueConstraint(
                fields=["question", "chapter", "topic"],
                name="qb_qtopic_q_ch_top_unique",
            ),
            models.UniqueConstraint(
                fields=["question"],
                condition=Q(is_primary=True, status="confirmed"),
                name="qb_qtopic_one_primary_confirmed",
            ),
        ]
        indexes = [
            models.Index(fields=["chapter", "status"], name="qb_qtopic_ch_stat_idx"),
            models.Index(fields=["subject_key", "chapter_key"], name="qb_qtopic_keys_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.question.public_id} -> {self.chapter_key} (primary={self.is_primary})"


class Tag(UUIDModel):
    class Kind(models.TextChoices):
        TOPIC = "topic", "Topic"
        EXAM = "exam", "Exam"
        FEATURE = "feature", "Feature"
        SYSTEM = "system", "System"

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        PENDING = "pending", "Pending approval"
        RETIRED = "retired", "Retired"

    slug = models.SlugField(max_length=80, unique=True)
    name = models.CharField(max_length=120)
    course = models.ForeignKey("syllabus.Course", null=True, blank=True, on_delete=models.RESTRICT, related_name="+")
    kind = models.CharField(max_length=32, choices=Kind.choices, default=Kind.TOPIC)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.ACTIVE)
    created_by = models.UUIDField(null=True, blank=True)

    class Meta:
        db_table = "questionbank_tag"
        ordering = ["slug"]

    def __str__(self) -> str:
        return self.slug


class QuestionTag(TimeStampedModel):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name="question_tags")
    tag = models.ForeignKey(Tag, on_delete=models.CASCADE, related_name="tagged_questions")

    class Meta:
        db_table = "questionbank_questiontag"
        constraints = [
            models.UniqueConstraint(fields=["question", "tag"], name="qb_qtag_unique"),
        ]

    def __str__(self) -> str:
        return f"{self.question_id}:{self.tag_id}"


class VersionMedia(TimeStampedModel):
    class Usage(models.TextChoices):
        STEM = "stem", "Stem"
        OPTION = "option", "Option"
        EXPLANATION = "explanation", "Explanation"
        RUBRIC = "rubric", "Rubric"

    version = models.ForeignKey(QuestionVersion, on_delete=models.CASCADE, related_name="media")
    attachment = models.ForeignKey("media.Attachment", on_delete=models.CASCADE, related_name="+")
    usage = models.CharField(max_length=32, choices=Usage.choices, default=Usage.STEM)
    alt_text = models.CharField(max_length=300)

    class Meta:
        db_table = "questionbank_versionmedia"
        constraints = [
            models.UniqueConstraint(fields=["version", "attachment"], name="qb_vermedia_unique"),
        ]
        indexes = [
            models.Index(fields=["attachment"], name="qb_vermedia_att_idx"),
        ]

    def __str__(self) -> str:
        return f"Media {self.attachment_id} for v{self.version_id}"


class Fingerprint(TimeStampedModel):
    question = models.OneToOneField(Question, primary_key=True, on_delete=models.CASCADE, related_name="fingerprint")
    version_id = models.UUIDField()
    fp_exact = models.CharField(max_length=64, db_index=True)
    fp_template = models.CharField(max_length=64, db_index=True)
    simhash = models.BigIntegerField()
    b0 = models.SmallIntegerField(db_index=True)
    b1 = models.SmallIntegerField(db_index=True)
    b2 = models.SmallIntegerField(db_index=True)
    b3 = models.SmallIntegerField(db_index=True)
    scope_owner = models.UUIDField(null=True, blank=True, db_index=True)
    kind = models.CharField(max_length=32, blank=True, default="")
    course_id = models.UUIDField(null=True, blank=True)

    class Meta:
        db_table = "questionbank_fingerprint"

    def __str__(self) -> str:
        return f"Fingerprint({self.question_id})"


class DuplicateLink(UUIDModel):
    class Kind(models.TextChoices):
        EXACT = "exact", "Exact match"
        NEAR = "near", "Near duplicate"
        VARIANT = "variant", "Figure variant"

    class State(models.TextChoices):
        SUSPECTED = "suspected", "Suspected"
        CONFIRMED = "confirmed", "Confirmed duplicate"
        NOT_DUPLICATE = "not_duplicate", "Not duplicate"
        MERGED = "merged", "Merged"

    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name="duplicates_as_primary")
    other_question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name="duplicates_as_other")
    kind = models.CharField(max_length=16, choices=Kind.choices, default=Kind.EXACT)
    score = models.DecimalField(max_digits=4, decimal_places=3)
    state = models.CharField(max_length=16, choices=State.choices, default=State.SUSPECTED)
    detected_at = models.DateTimeField(auto_now_add=True)
    decided_by = models.UUIDField(null=True, blank=True)
    decided_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "questionbank_duplicatelink"
        constraints = [
            models.UniqueConstraint(fields=["question", "other_question"], name="qb_duplink_q_other_unique"),
        ]
        indexes = [
            models.Index(fields=["state", "kind"], name="qb_duplink_state_kind_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.question_id} <-> {self.other_question_id} ({self.kind}, {self.state})"


class Review(UUIDModel):
    class Kind(models.TextChoices):
        NEW_PUBLIC = "new_public", "New public submission"
        EDIT_PUBLIC = "edit_public", "Edit to public question"
        SECOND_REVIEW = "second_review", "Second review"
        INGESTED = "ingested", "Ingested from feed"
        REPORT_FOLLOWUP = "report_followup", "Followup on error report"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        CLAIMED = "claimed", "Claimed"
        APPROVED = "approved", "Approved"
        CHANGES_REQUESTED = "changes_requested", "Changes requested"
        REJECTED = "rejected", "Rejected"
        WITHDRAWN = "withdrawn", "Withdrawn"
        SUPERSEDED = "superseded", "Superseded"

    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name="reviews")
    version = models.OneToOneField(QuestionVersion, on_delete=models.CASCADE, related_name="review")
    kind = models.CharField(max_length=32, choices=Kind.choices, default=Kind.NEW_PUBLIC)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    submitted_by = models.UUIDField(null=True, blank=True)
    claimed_by = models.UUIDField(null=True, blank=True)
    claimed_until = models.DateTimeField(null=True, blank=True)
    decided_by = models.UUIDField(null=True, blank=True)
    decided_at = models.DateTimeField(null=True, blank=True)
    decision_code = models.CharField(max_length=32, blank=True, default="")
    decision_note = models.TextField(blank=True, default="")
    field_comments = models.JSONField(default=list, blank=True)
    checks = models.JSONField(default=dict, blank=True)
    flags = models.JSONField(default=list, blank=True)
    priority = models.SmallIntegerField(default=0)
    submitted_at = models.DateTimeField(default=timezone.now)
    sla_due_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "questionbank_review"
        indexes = [
            models.Index(fields=["status", "-priority", "submitted_at"], name="qb_review_queue_idx"),
            models.Index(fields=["question"], name="qb_review_q_idx"),
            models.Index(fields=["decided_by", "-decided_at"], name="qb_review_decider_idx"),
        ]

    def __str__(self) -> str:
        return f"Review for {self.question.public_id} v{self.version.version_no} ({self.status})"


class Report(UUIDModel):
    class Kind(models.TextChoices):
        WRONG_ANSWER = "wrong_answer", "Wrong answer"
        TYPO = "typo", "Typo"
        UNCLEAR = "unclear", "Unclear question"
        OUTDATED_LAW = "outdated_law", "Outdated law"
        WRONG_MAPPING = "wrong_mapping", "Wrong chapter or topic"
        DUPLICATE = "duplicate", "Duplicate question"
        COPYRIGHT = "copyright", "Copyright issue"
        OFFENSIVE = "offensive", "Offensive content"
        OTHER = "other", "Other"

    class Status(models.TextChoices):
        OPEN = "open", "Open"
        ACCEPTED = "accepted", "Accepted"
        REJECTED = "rejected", "Rejected"
        FIXED = "fixed", "Fixed"
        DUPLICATE = "duplicate", "Duplicate report"

    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name="reports")
    version = models.ForeignKey(QuestionVersion, on_delete=models.CASCADE, related_name="reports")
    reporter_user_id = models.UUIDField(db_index=True)
    kind = models.CharField(max_length=32, choices=Kind.choices)
    message = models.TextField(blank=True, default="")
    proposed_option_ids = models.JSONField(default=list, blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.OPEN)
    resolved_by = models.UUIDField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolution_note = models.TextField(blank=True, default="")
    fixed_version = models.ForeignKey(
        QuestionVersion, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    class Meta:
        db_table = "questionbank_report"
        constraints = [
            models.UniqueConstraint(
                fields=["question", "reporter_user_id", "kind"],
                condition=Q(status="open"),
                name="qb_report_unique_open",
            ),
        ]
        indexes = [
            models.Index(fields=["status", "created_at"], name="qb_report_status_date_idx"),
            models.Index(fields=["question", "status"], name="qb_report_q_status_idx"),
        ]

    def __str__(self) -> str:
        return f"Report {self.kind} on {self.question.public_id} ({self.status})"


class Verification(UUIDModel):
    class Level(models.TextChoices):
        EDITOR = "editor", "Artha Editor"
        FACULTY = "faculty", "Subject Faculty"
        INSTITUTE_SOURCE = "institute_source", "Institute Solution Match"

    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name="verifications")
    version = models.ForeignKey(QuestionVersion, on_delete=models.CASCADE, related_name="verifications")
    verified_by = models.UUIDField(db_index=True)
    level = models.CharField(max_length=32, choices=Level.choices, default=Level.EDITOR)
    source_label = models.CharField(max_length=200)
    source_url = models.URLField(blank=True, default="")
    display_name = models.CharField(max_length=120, null=True, blank=True)  # noqa: DJ001
    verified_at = models.DateTimeField(default=timezone.now)
    revoked_at = models.DateTimeField(null=True, blank=True)
    revoke_reason = models.TextField(blank=True, default="")

    class Meta:
        db_table = "questionbank_verification"
        constraints = [
            models.UniqueConstraint(
                fields=["version"],
                condition=Q(revoked_at__isnull=True),
                name="qb_verify_active_unique",
            ),
        ]

    def __str__(self) -> str:
        return f"Verification for {self.version_id} ({self.level})"


class Takedown(UUIDModel):
    class Channel(models.TextChoices):
        WEB_FORM = "web_form", "Web form"
        EMAIL = "email", "Email"
        COURT_ORDER = "court_order", "Court order"

    class Status(models.TextChoices):
        RECEIVED = "received", "Received"
        VALIDATED = "validated", "Validated"
        ACTIONED = "actioned", "Actioned"
        COUNTER_NOTICE = "counter_notice", "Counter-notice received"
        RESTORED = "restored", "Restored"
        REJECTED = "rejected", "Rejected"
        EXPIRED = "expired", "Expired"

    reference = models.CharField(max_length=32, unique=True)
    received_at = models.DateTimeField(default=timezone.now)
    channel = models.CharField(max_length=32, choices=Channel.choices, default=Channel.WEB_FORM)
    complainant_name = models.CharField(max_length=120)
    complainant_email = models.EmailField()
    claimed_work = models.TextField()
    proof_note = models.TextField(blank=True, default="")
    statement_signed = models.BooleanField(default=False)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.RECEIVED)
    sla_due_at = models.DateTimeField(null=True, blank=True)
    actioned_at = models.DateTimeField(null=True, blank=True)
    actioned_by = models.UUIDField(null=True, blank=True)
    uploader_notified_at = models.DateTimeField(null=True, blank=True)
    counter_notice_at = models.DateTimeField(null=True, blank=True)
    counter_notice_text = models.TextField(blank=True, default="")
    court_order_due_at = models.DateTimeField(null=True, blank=True)
    restored_at = models.DateTimeField(null=True, blank=True)
    ingestion_takedown_id = models.UUIDField(null=True, blank=True)

    class Meta:
        db_table = "questionbank_takedown"
        indexes = [
            models.Index(fields=["status", "sla_due_at"], name="qb_td_status_sla_idx"),
        ]

    def __str__(self) -> str:
        return f"Takedown {self.reference} ({self.status})"


class TakedownItem(TimeStampedModel):
    takedown = models.ForeignKey(Takedown, on_delete=models.CASCADE, related_name="items")
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name="takedown_items")

    class Meta:
        db_table = "questionbank_takedownitem"
        constraints = [
            models.UniqueConstraint(fields=["takedown", "question"], name="qb_tditem_unique"),
        ]

    def __str__(self) -> str:
        return f"{self.takedown_id}:{self.question_id}"


class Contributor(TimeStampedModel):
    user_id = models.UUIDField(primary_key=True)
    terms_version = models.CharField(max_length=16, default="2026-10")
    terms_accepted_at = models.DateTimeField(default=timezone.now)
    level = models.SmallIntegerField(default=0)
    points = models.IntegerField(default=0)
    approved_count = models.IntegerField(default=0)
    rejected_count = models.IntegerField(default=0)
    takedown_count = models.IntegerField(default=0)
    strikes = models.SmallIntegerField(default=0)
    suspended_until = models.DateTimeField(null=True, blank=True)
    display_name = models.CharField(max_length=120, null=True, blank=True)  # noqa: DJ001
    show_credit = models.BooleanField(default=False)
    plan_code = models.CharField(max_length=32, default="free")
    last_submission_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "questionbank_contributor"

    def __str__(self) -> str:
        return f"Contributor {self.user_id} (Level {self.level})"


class QuotaPlan(TimeStampedModel):
    plan_code = models.CharField(max_length=32, primary_key=True)
    max_questions = models.IntegerField(default=500)
    max_media_mb = models.IntegerField(default=100)
    max_public_submissions_per_day = models.IntegerField(default=20)
    max_collections = models.IntegerField(default=50)
    max_items_per_collection = models.IntegerField(default=200)
    max_share_links = models.IntegerField(default=50)
    max_imports_per_day = models.IntegerField(default=5)
    max_import_rows = models.IntegerField(default=500)
    max_sheet_pages_per_month = models.IntegerField(default=50)
    max_sheet_mb = models.IntegerField(default=200)
    level_multipliers = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "questionbank_quotaplan"

    def __str__(self) -> str:
        return f"QuotaPlan({self.plan_code})"


class AuditLog(models.Model):
    id = models.BigAutoField(primary_key=True)
    actor_id = models.UUIDField(null=True, blank=True)
    entity_type = models.CharField(max_length=64)
    entity_id = models.UUIDField()
    action = models.CharField(max_length=64)
    before = models.JSONField(null=True, blank=True)
    after = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "questionbank_auditlog"
        indexes = [
            models.Index(fields=["entity_type", "entity_id", "-created_at"], name="qb_audit_entity_idx"),
        ]

    def __str__(self) -> str:
        return f"Audit {self.action} on {self.entity_type}:{self.entity_id}"


class Collection(UUIDModel):
    class Kind(models.TextChoices):
        CUSTOM = "custom", "Custom user collection"
        CURATED = "curated", "Curated platform collection"

    class Visibility(models.TextChoices):
        PRIVATE = "private", "Private"
        LINK = "link", "Shared via link"
        PUBLIC = "public", "Public"

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        ARCHIVED = "archived", "Archived"

    owner_user_id = models.UUIDField(null=True, blank=True, db_index=True)
    kind = models.CharField(max_length=16, choices=Kind.choices, default=Kind.CUSTOM)
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=120, null=True, blank=True, unique=True)
    description_md = models.TextField(blank=True, default="")
    visibility = models.CharField(max_length=16, choices=Visibility.choices, default=Visibility.PRIVATE)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.ACTIVE)
    course = models.ForeignKey("syllabus.Course", null=True, blank=True, on_delete=models.RESTRICT, related_name="+")
    level = models.ForeignKey("syllabus.Level", null=True, blank=True, on_delete=models.RESTRICT, related_name="+")
    subject_key = models.CharField(max_length=80, null=True, blank=True)  # noqa: DJ001
    item_count = models.IntegerField(default=0)
    meta = models.JSONField(default=dict, blank=True)
    meta_schema = models.SmallIntegerField(default=1)
    published_at = models.DateTimeField(null=True, blank=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "questionbank_collection"
        indexes = [
            models.Index(fields=["owner_user_id", "status", "-updated_at"], name="qb_coll_owner_stat_idx"),
            models.Index(fields=["visibility", "kind", "-published_at"], name="qb_coll_vis_kind_idx"),
        ]

    def __str__(self) -> str:
        return self.title


class CollectionItem(TimeStampedModel):
    collection = models.ForeignKey(Collection, on_delete=models.CASCADE, related_name="items")
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name="collection_items")
    position = models.IntegerField(default=1024)
    note = models.TextField(blank=True, default="")
    added_by = models.UUIDField(null=True, blank=True)
    added_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "questionbank_collectionitem"
        ordering = ["position"]
        constraints = [
            models.UniqueConstraint(fields=["collection", "question"], name="qb_collitem_unique"),
        ]
        indexes = [
            models.Index(fields=["collection", "position"], name="qb_collitem_pos_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.collection_id}:{self.question_id}"


class SavedFilter(UUIDModel):
    user_id = models.UUIDField(db_index=True)
    name = models.CharField(max_length=120)
    spec = models.JSONField(default=dict)
    spec_schema = models.SmallIntegerField(default=1)
    is_default = models.BooleanField(default=False)
    notify_new = models.BooleanField(default=False)
    last_seen_at = models.DateTimeField(null=True, blank=True)
    last_count = models.IntegerField(default=0)

    class Meta:
        db_table = "questionbank_savedfilter"
        constraints = [
            models.UniqueConstraint(fields=["user_id", "name"], name="qb_savedfilter_user_name_unique"),
        ]

    def __str__(self) -> str:
        return f"{self.user_id}: {self.name}"


class ShareLink(UUIDModel):
    class Kind(models.TextChoices):
        COLLECTION = "collection", "Collection"
        QUESTION = "question", "Single question"
        FILTER = "filter", "Saved filter"

    token = models.CharField(max_length=32, unique=True, db_index=True)
    kind = models.CharField(max_length=16, choices=Kind.choices)
    collection = models.ForeignKey(Collection, null=True, blank=True, on_delete=models.CASCADE, related_name="+")
    question = models.ForeignKey(Question, null=True, blank=True, on_delete=models.CASCADE, related_name="+")
    spec = models.JSONField(null=True, blank=True)
    created_by = models.UUIDField(db_index=True)
    settings = models.JSONField(default=dict, blank=True)
    title_override = models.CharField(max_length=200, blank=True, default="")
    expires_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    view_count = models.IntegerField(default=0)
    start_count = models.IntegerField(default=0)
    last_used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "questionbank_sharelink"
        indexes = [
            models.Index(fields=["created_by", "revoked_at"], name="qb_sharelink_owner_idx"),
        ]

    def __str__(self) -> str:
        return f"ShareLink({self.token}, {self.kind})"


class ImportJob(UUIDModel):
    class Format(models.TextChoices):
        CSV = "csv", "CSV"
        DOCX = "docx", "DOCX"
        PDF = "pdf", "PDF"
        IMAGE = "image", "Image"
        JSON = "json", "JSON"
        QTI = "qti", "QTI"

    class Status(models.TextChoices):
        UPLOADED = "uploaded", "Uploaded"
        PARSING = "parsing", "Parsing"
        NEEDS_MAPPING = "needs_mapping", "Needs mapping"
        REVIEW = "review", "Review"
        COMMITTING = "committing", "Committing"
        DONE = "done", "Done"
        FAILED = "failed", "Failed"
        CANCELLED = "cancelled", "Cancelled"

    user_id = models.UUIDField(db_index=True)
    format = models.CharField(max_length=16, choices=Format.choices, default=Format.CSV)
    purpose = models.CharField(max_length=16, default="platform")
    attachment = models.ForeignKey(
        "media.Attachment", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.UPLOADED)
    mapping_profile = models.JSONField(default=dict, blank=True)
    counts = models.JSONField(default=dict, blank=True)
    error_attachment_id = models.UUIDField(null=True, blank=True)
    ai_cost_paise = models.IntegerField(default=0)
    finished_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "questionbank_importjob"

    def __str__(self) -> str:
        return f"ImportJob {self.id} ({self.format}, {self.status})"


class ImportRow(UUIDModel):
    class Status(models.TextChoices):
        OK = "ok", "OK"
        WARNING = "warning", "Warning"
        ERROR = "error", "Error"
        DUPLICATE = "duplicate", "Duplicate"
        SKIPPED = "skipped", "Skipped"
        COMMITTED = "committed", "Committed"

    job = models.ForeignKey(ImportJob, on_delete=models.CASCADE, related_name="rows")
    row_no = models.IntegerField()
    raw = models.JSONField(default=dict)
    parsed = models.JSONField(null=True, blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.OK)
    errors = models.JSONField(default=list, blank=True)
    duplicate_of = models.UUIDField(null=True, blank=True)
    question = models.ForeignKey(Question, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")

    class Meta:
        db_table = "questionbank_importrow"
        constraints = [
            models.UniqueConstraint(fields=["job", "row_no"], name="qb_importrow_job_row_unique"),
        ]
        indexes = [
            models.Index(fields=["job", "status", "row_no"], name="qb_importrow_job_stat_idx"),
        ]

    def __str__(self) -> str:
        return f"ImportRow {self.job_id}:{self.row_no} ({self.status})"


class ExportJob(UUIDModel):
    class Format(models.TextChoices):
        JSON = "json", "JSON"
        CSV = "csv", "CSV"
        QTI = "qti", "QTI"

    class Status(models.TextChoices):
        QUEUED = "queued", "Queued"
        RUNNING = "running", "Running"
        DONE = "done", "Done"
        FAILED = "failed", "Failed"
        EXPIRED = "expired", "Expired"

    user_id = models.UUIDField(db_index=True)
    format = models.CharField(max_length=16, choices=Format.choices, default=Format.JSON)
    scope = models.JSONField(default=dict)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.QUEUED)
    attachment = models.ForeignKey(
        "media.Attachment", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    row_count = models.IntegerField(default=0)
    expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "questionbank_exportjob"

    def __str__(self) -> str:
        return f"ExportJob {self.id} ({self.format}, {self.status})"


class QuestionStats(TimeStampedModel):
    question = models.OneToOneField(Question, primary_key=True, on_delete=models.CASCADE, related_name="stats")
    attempts = models.IntegerField(default=0)
    correct = models.IntegerField(default=0)
    partial = models.IntegerField(default=0)
    skipped = models.IntegerField(default=0)
    avg_time_ms = models.IntegerField(default=0)
    p_value = models.DecimalField(max_digits=4, decimal_places=3, null=True, blank=True)
    open_reports = models.SmallIntegerField(default=0)
    bookmark_count = models.IntegerField(default=0)
    calculated_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "questionbank_questionstats"

    def __str__(self) -> str:
        return f"Stats for {self.question_id}: {self.attempts} attempts"
