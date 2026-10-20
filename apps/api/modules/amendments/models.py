from __future__ import annotations

import secrets
from decimal import Decimal

from django.db import models
from django.db.models import Q
from django.utils import timezone

from core.models import UUIDModel

CROCKFORD_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


def generate_public_id(length: int = 10) -> str:
    """Generate a Crockford Base32 10-character string (excludes I, L, O, U)."""
    return "".join(secrets.choice(CROCKFORD_ALPHABET) for _ in range(length))


class Amendment(UUIDModel):
    """
    Stable document stream representing an Institute amendment announcement (ERD Section 2.1).
    One document can have multiple revisions (re-issues, corrections).
    """

    class Kind(models.TextChoices):
        STATUTORY_UPDATE = "statutory_update", "Statutory Update"
        JUDICIAL_UPDATE = "judicial_update", "Judicial Update"
        ACADEMIC_UPDATE = "academic_update", "Academic Update"
        LEGISLATIVE_AMENDMENT = "legislative_amendment", "Legislative Amendment"
        STANDARDS_UPDATE = "standards_update", "Standards Update"
        CORRIGENDUM = "corrigendum", "Corrigendum"
        APPLICABILITY_NOTICE = "applicability_notice", "Applicability Notice"
        OTHER = "other", "Other"

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        RETRACTED = "retracted", "Retracted"
        TAKEN_DOWN = "taken_down", "Taken Down"

    public_id = models.CharField(max_length=10, unique=True, default=generate_public_id, editable=False)
    slug = models.SlugField(max_length=150, unique=True)
    course = models.ForeignKey("syllabus.Course", on_delete=models.RESTRICT, related_name="amendments")
    level = models.ForeignKey("syllabus.Level", on_delete=models.RESTRICT, related_name="amendments")
    doc_key = models.CharField(max_length=120)
    kind = models.CharField(max_length=32, choices=Kind.choices, default=Kind.STATUTORY_UPDATE)
    title = models.CharField(max_length=200)
    short_title = models.CharField(max_length=120, blank=True, default="")
    issuer_label = models.CharField(max_length=120)
    landing_url = models.URLField(max_length=500, blank=True, default="")
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.ACTIVE)

    live_revision = models.ForeignKey("Revision", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    current_revision = models.ForeignKey("Revision", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")

    first_released_at = models.DateTimeField(null=True, blank=True)
    last_released_at = models.DateTimeField(null=True, blank=True)
    seo_indexable = models.BooleanField(default=True)
    source_id = models.UUIDField(null=True, blank=True)
    created_by = models.UUIDField(null=True, blank=True)

    class Meta:
        db_table = "amendments_amendment"
        ordering = ["-last_released_at", "-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["level", "doc_key"], name="amend_lvl_dockey_uniq"),
            models.CheckConstraint(
                condition=Q(live_revision__isnull=True) | Q(status="active"),
                name="amend_live_rev_must_be_active",
            ),
        ]
        indexes = [
            models.Index(fields=["level", "status", "-last_released_at"], name="amend_lvl_stat_rel_idx"),
            models.Index(fields=["course", "level"], name="amend_crs_lvl_idx"),
            models.Index(fields=["source_id"], name="amend_src_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.short_title or self.title} ({self.public_id})"


class Revision(UUIDModel):
    """
    Issued file revision of an Amendment (ERD Section 2.2).
    Unit of review and atomic release.
    """

    class State(models.TextChoices):
        STAGED = "staged", "Staged"
        IN_REVIEW = "in_review", "In Review"
        LIVE = "live", "Live"
        SUPERSEDED = "superseded", "Superseded"
        RETRACTED = "retracted", "Retracted"
        REJECTED = "rejected", "Rejected"

    class Kind(models.TextChoices):
        INITIAL = "initial", "Initial Release"
        REISSUE = "reissue", "Institute Re-issue"
        OUR_CORRECTION = "our_correction", "Editorial Correction"
        CORRIGENDUM = "corrigendum", "Institute Corrigendum"

    class RetractionReason(models.TextChoices):
        INSTITUTE_WITHDREW = "institute_withdrew", "Institute Withdrew"
        EXTRACTION_ERROR = "extraction_error", "Extraction Error"
        LEGAL_REQUEST = "legal_request", "Legal Request"
        SUPERSEDED_BY_LATER = "superseded_by_later", "Superseded by Later Document"
        OTHER = "other", "Other"

    amendment = models.ForeignKey(Amendment, on_delete=models.CASCADE, related_name="revisions")
    revision_no = models.PositiveIntegerField(default=1)
    state = models.CharField(max_length=16, choices=State.choices, default=State.STAGED)
    revision_kind = models.CharField(max_length=20, choices=Kind.choices, default=Kind.INITIAL)
    issued_on = models.DateField(default=timezone.now)
    official_url = models.URLField(max_length=500, blank=True, default="")
    doc_sha256 = models.CharField(max_length=64, blank=True, default="")
    page_count = models.PositiveSmallIntegerField(null=True, blank=True)

    extraction = models.JSONField(default=dict, blank=True)
    checks = models.JSONField(default=dict, blank=True)
    diff_summary = models.JSONField(default=dict, blank=True)

    reviewed_by = models.UUIDField(null=True, blank=True)
    released_by = models.UUIDField(null=True, blank=True)
    released_at = models.DateTimeField(null=True, blank=True)

    supersedes = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.SET_NULL, related_name="superseded_by"
    )
    retraction_reason = models.CharField(max_length=32, choices=RetractionReason.choices, blank=True, default="")

    class Meta:
        db_table = "amendments_revision"
        ordering = ["amendment", "-revision_no"]
        constraints = [
            models.UniqueConstraint(fields=["amendment", "revision_no"], name="amend_rev_no_uniq"),
            models.UniqueConstraint(
                fields=["amendment"],
                condition=Q(state="live"),
                name="amend_one_live_rev_uniq",
            ),
            models.UniqueConstraint(
                fields=["amendment"],
                condition=Q(state__in=["staged", "in_review"]),
                name="amend_one_open_rev_uniq",
            ),
        ]
        indexes = [
            models.Index(fields=["amendment", "state"], name="amend_rev_state_idx"),
            models.Index(fields=["state", "-released_at"], name="amend_rev_rel_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.amendment.slug} r{self.revision_no} ({self.state})"


class RevisionSubject(UUIDModel):
    """
    Paper scope of a revision across schemes (ERD Section 2.3).
    """

    revision = models.ForeignKey(Revision, on_delete=models.CASCADE, related_name="subjects")
    subject = models.ForeignKey("syllabus.Subject", on_delete=models.PROTECT, related_name="+")
    subject_key = models.CharField(max_length=100)
    scheme = models.ForeignKey("syllabus.Scheme", on_delete=models.PROTECT, related_name="+")
    level = models.ForeignKey("syllabus.Level", on_delete=models.PROTECT, related_name="+")

    class Meta:
        db_table = "amendments_revisionsubject"
        constraints = [
            models.UniqueConstraint(fields=["revision", "subject"], name="rev_subj_uniq"),
        ]
        indexes = [
            models.Index(fields=["subject_key", "level"], name="rev_subj_key_lvl_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.revision_id}: {self.subject_key}"


class RevisionTerm(UUIDModel):
    """
    Exam term applicability of a revision (ERD Section 2.4).
    """

    class Applicability(models.TextChoices):
        APPLIES = "applies", "Applies"
        EXCLUDED = "excluded", "Excluded"

    class Origin(models.TextChoices):
        INSTITUTE_EXPLICIT = "institute_explicit", "Institute Explicit"
        INSTITUTE_IMPLIED = "institute_implied", "Institute Implied"
        EDITOR_ENTRY = "editor_entry", "Editor Entry"

    revision = models.ForeignKey(Revision, on_delete=models.CASCADE, related_name="terms")
    term_code = models.CharField(max_length=16)  # e.g., "2026-05"
    exam_term = models.ForeignKey(
        "syllabus.ExamTerm", null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    applicability = models.CharField(max_length=16, choices=Applicability.choices, default=Applicability.APPLIES)
    cutoff_date = models.DateField(null=True, blank=True)
    cutoff_note = models.TextField(blank=True, default="")
    source_page = models.PositiveSmallIntegerField(null=True, blank=True)
    origin = models.CharField(max_length=24, choices=Origin.choices, default=Origin.INSTITUTE_EXPLICIT)
    confirmed_by = models.UUIDField(null=True, blank=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "amendments_revisionterm"
        ordering = ["term_code"]
        constraints = [
            models.UniqueConstraint(fields=["revision", "term_code"], name="rev_term_uniq"),
        ]
        indexes = [
            models.Index(fields=["term_code", "applicability"], name="rev_term_code_app_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.revision_id}: {self.term_code} ({self.applicability})"


class Change(UUIDModel):
    """
    Stable identity of one change card across revisions (ERD Section 2.5).
    """

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        WITHDRAWN = "withdrawn", "Withdrawn"
        SUPERSEDED = "superseded", "Superseded"

    public_id = models.CharField(max_length=10, unique=True, default=generate_public_id, editable=False)
    amendment = models.ForeignKey(Amendment, on_delete=models.CASCADE, related_name="changes")
    card_key = models.CharField(max_length=120)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.ACTIVE)

    live_version = models.ForeignKey(
        "ChangeVersion", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    current_version = models.ForeignKey(
        "ChangeVersion", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    needs_attention = models.BooleanField(default=False)
    corrects_change = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.SET_NULL, related_name="corrigenda"
    )

    class Meta:
        db_table = "amendments_change"
        constraints = [
            models.UniqueConstraint(fields=["amendment", "card_key"], name="amend_card_key_uniq"),
        ]
        indexes = [
            models.Index(fields=["amendment", "status"], name="change_amend_stat_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.card_key} ({self.public_id})"


class ChangeVersion(UUIDModel):
    """
    Content of a change card within a specific revision (ERD Section 2.6).
    """

    class ChangeType(models.TextChoices):
        ADDITION = "addition", "Addition"
        DELETION = "deletion", "Deletion"
        MODIFICATION = "modification", "Modification"
        NEW_STANDARD = "new_standard", "New Standard / Law"
        CLARIFICATION = "clarification", "Clarification / Scope Statement"

    class Materiality(models.TextChoices):
        HIGH = "high", "High"
        NORMAL = "normal", "Normal"
        LOW = "low", "Low"

    class RevisionEffect(models.TextChoices):
        UNCHANGED = "unchanged", "Unchanged"
        UPDATED = "updated", "Updated"
        NEW = "new", "New"
        REMOVED = "removed", "Removed"

    change = models.ForeignKey(Change, on_delete=models.CASCADE, related_name="versions")
    revision = models.ForeignKey(Revision, on_delete=models.CASCADE, related_name="change_versions")
    change_type = models.CharField(max_length=24, choices=ChangeType.choices, default=ChangeType.MODIFICATION)
    law_key = models.CharField(max_length=64, blank=True, default="")
    provision_label = models.CharField(max_length=120)
    provision_keys = models.JSONField(default=list, blank=True)
    title = models.CharField(max_length=200)

    summary_old = models.TextField(blank=True, default="")
    summary_new = models.TextField(blank=True, default="")
    effective_from_term_code = models.CharField(max_length=16, blank=True, default="")
    materiality = models.CharField(max_length=16, choices=Materiality.choices, default=Materiality.NORMAL)
    source_page = models.PositiveSmallIntegerField(null=True, blank=True)
    anchor = models.JSONField(default=dict, blank=True)
    evidence_quote = models.TextField(blank=True, default="")  # admin evidence only

    confidence = models.DecimalField(max_digits=4, decimal_places=3, default=Decimal("1.000"))
    flags = models.JSONField(default=list, blank=True)
    revision_effect = models.CharField(max_length=16, choices=RevisionEffect.choices, default=RevisionEffect.NEW)
    is_live = models.BooleanField(default=False)
    ingestion_item_version_id = models.UUIDField(null=True, blank=True)

    class Meta:
        db_table = "amendments_changeversion"
        constraints = [
            models.UniqueConstraint(fields=["change", "revision"], name="change_rev_uniq"),
        ]
        indexes = [
            models.Index(fields=["revision", "is_live"], name="cver_rev_live_idx"),
            models.Index(fields=["change_type"], name="cver_type_idx"),
            models.Index(fields=["effective_from_term_code"], name="cver_eff_term_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.provision_label}: {self.title}"


class ChangeMap(UUIDModel):
    """
    Mapping of a change version to syllabus paper, chapter, and topic (ERD Section 2.7).
    """

    class Status(models.TextChoices):
        SUGGESTED = "suggested", "Suggested"
        CONFIRMED = "confirmed", "Confirmed"
        REJECTED = "rejected", "Rejected"

    class Origin(models.TextChoices):
        RULES = "rules", "Rules"
        AI = "ai", "AI Suggested"
        MANUAL = "manual", "Manual Entry"

    change_version = models.ForeignKey(ChangeVersion, on_delete=models.CASCADE, related_name="maps")
    subject = models.ForeignKey("syllabus.Subject", on_delete=models.PROTECT, related_name="+")
    chapter = models.ForeignKey("syllabus.Chapter", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    topic = models.ForeignKey("syllabus.Topic", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    scheme = models.ForeignKey("syllabus.Scheme", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    subject_key = models.CharField(max_length=100)
    chapter_key = models.CharField(max_length=120, blank=True, default="")
    is_primary = models.BooleanField(default=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.CONFIRMED)
    origin = models.CharField(max_length=16, choices=Origin.choices, default=Origin.MANUAL)
    confidence = models.DecimalField(max_digits=4, decimal_places=3, default=Decimal("1.000"))

    class Meta:
        db_table = "amendments_changemap"
        indexes = [
            models.Index(fields=["chapter", "status"], name="cmap_chp_stat_idx"),
            models.Index(fields=["subject", "status"], name="cmap_subj_stat_idx"),
            models.Index(fields=["subject_key", "chapter_key"], name="cmap_keys_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.change_version_id} -> {self.subject_key}/{self.chapter_key}"


class CardState(UUIDModel):
    """
    Student interaction state per change card (ERD Section 2.9).
    """

    user_id = models.UUIDField(db_index=True)
    change = models.ForeignKey(Change, on_delete=models.CASCADE, related_name="user_states")
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_version = models.ForeignKey(
        ChangeVersion, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    saved = models.BooleanField(default=False)
    first_seen_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "amendments_cardstate"
        constraints = [
            models.UniqueConstraint(fields=["user_id", "change"], name="user_change_state_uniq"),
        ]
        indexes = [
            models.Index(fields=["user_id", "-reviewed_at"], name="cardstate_usr_rev_idx"),
            models.Index(fields=["user_id", "saved"], name="cardstate_usr_saved_idx"),
        ]

    def __str__(self) -> str:
        return f"User({self.user_id}) -> Card({self.change_id})"


class AmendmentAuditLog(UUIDModel):
    """
    Immutable audit trail for review, release, and retraction actions (ERD Section 2.11).
    """

    amendment = models.ForeignKey(Amendment, on_delete=models.CASCADE, related_name="audit_logs")
    revision = models.ForeignKey(Revision, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    change = models.ForeignKey(Change, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    actor_id = models.UUIDField(null=True, blank=True)
    action = models.CharField(max_length=64)  # e.g., "create_draft", "stage_card", "release", "retract"
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "amendments_auditlog"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["amendment", "-created_at"], name="amend_audit_amend_idx"),
            models.Index(fields=["action", "-created_at"], name="amend_audit_action_idx"),
        ]

    def __str__(self) -> str:
        return f"Audit({self.amendment.public_id}, {self.action})"
