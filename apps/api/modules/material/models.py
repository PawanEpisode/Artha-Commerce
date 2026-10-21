"""
Models for F-12 Institute Study Material (MAT).
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from django.db import models


class Provider(models.Model):
    class Kind(models.TextChoices):
        INSTITUTE = "institute", "Institute"
        COACHING = "coaching", "Coaching"
        PUBLISHER = "publisher", "Publisher"

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        PENDING = "pending", "Pending"
        MERGED = "merged", "Merged"
        BLOCKED = "blocked", "Blocked"
        ARCHIVED = "archived", "Archived"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    slug = models.CharField(max_length=64, unique=True)
    name = models.CharField(max_length=120)
    normalised_name = models.CharField(max_length=120, db_index=True)
    kind = models.CharField(max_length=32, choices=Kind.choices)
    ingestion_source_id = models.UUIDField(unique=True)
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.ACTIVE)
    merged_into = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.SET_NULL, related_name="merged_providers"
    )
    website_url = models.URLField(max_length=500, null=True, blank=True)
    created_by_user_id = models.UUIDField(null=True, blank=True, db_index=True)
    reviewed_by = models.UUIDField(null=True, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    blocked_reason = models.CharField(max_length=32, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "material_provider"
        indexes = [
            models.Index(fields=["kind", "status"], name="mat_prov_kind_stat_idx"),
            models.Index(fields=["normalised_name"], name="mat_prov_norm_name_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.slug})"


class Work(models.Model):
    class Kind(models.TextChoices):
        MODULE = "module", "Module"
        BOOK = "book", "Book"
        QUESTION_BANK = "question_bank", "Question Bank"
        SUPPLEMENT = "supplement", "Supplement"
        CHECKLIST = "checklist", "Checklist"

    class Visibility(models.TextChoices):
        PUBLIC = "public", "Public"
        PRIVATE = "private", "Private"

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        ARCHIVED = "archived", "Archived"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    provider = models.ForeignKey(Provider, on_delete=models.RESTRICT, related_name="works")
    work_key = models.CharField(max_length=100, db_index=True)
    title = models.CharField(max_length=200)
    kind = models.CharField(max_length=32, choices=Kind.choices, default=Kind.MODULE)
    base_work = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.SET_NULL, related_name="supplements"
    )
    course_id = models.UUIDField(db_index=True)
    level_id = models.UUIDField(db_index=True)
    subject_key = models.CharField(max_length=80, db_index=True)
    subject_id = models.UUIDField(null=True, blank=True)
    owner_user_id = models.UUIDField(null=True, blank=True, db_index=True)
    visibility = models.CharField(max_length=16, choices=Visibility.choices, default=Visibility.PUBLIC)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.ACTIVE)
    level_cached = models.SmallIntegerField(default=1)
    item_count_cached = models.IntegerField(default=0)
    deleted_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "material_work"
        indexes = [
            models.Index(
                fields=["course_id", "level_id", "subject_key", "status"],
                name="mat_work_crs_lvl_subj_idx",
            ),
            models.Index(fields=["owner_user_id", "status"], name="mat_work_owner_idx"),
            models.Index(fields=["provider", "status"], name="mat_work_prov_idx"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["provider", "work_key", "owner_user_id"],
                name="uq_mat_work_provider_key_owner",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.title} ({self.work_key})"


class Edition(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        MATCHING = "matching", "Matching"
        READY = "ready", "Ready"
        CURRENT = "current", "Current"
        SUPERSEDED = "superseded", "Superseded"
        WITHDRAWN = "withdrawn", "Withdrawn"

    class WithdrawReason(models.TextChoices):
        OPT_OUT = "opt_out", "Opt Out"
        TAKEDOWN = "takedown", "Takedown"
        RIGHTS_LAPSED = "rights_lapsed", "Rights Lapsed"
        EDITORIAL = "editorial", "Editorial"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    work = models.ForeignKey(Work, on_delete=models.RESTRICT, related_name="editions")
    label = models.CharField(max_length=120)
    edition_date = models.DateField(null=True, blank=True)
    reprint_date = models.DateField(null=True, blank=True)
    applies_from_term = models.CharField(max_length=16)
    applies_to_term = models.CharField(max_length=16, null=True, blank=True)
    applies_from_ord = models.IntegerField(db_index=True)
    applies_to_ord = models.IntegerField(null=True, blank=True, db_index=True)
    applicability_note = models.TextField(default="", blank=True)
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.DRAFT)
    withdraw_reason = models.CharField(max_length=32, choices=WithdrawReason.choices, null=True, blank=True)
    source_url = models.URLField(max_length=500, null=True, blank=True)
    source_page_url = models.URLField(max_length=500, null=True, blank=True)
    page_offset = models.SmallIntegerField(default=0)
    source_snapshot_id = models.UUIDField(null=True, blank=True)
    source_sha256 = models.CharField(max_length=64, null=True, blank=True)
    version = models.IntegerField(default=1)
    import_job_id = models.UUIDField(null=True, blank=True)
    capabilities_at_publish = models.JSONField(default=list, blank=True)
    level_at_publish = models.SmallIntegerField(null=True, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)
    published_by = models.UUIDField(null=True, blank=True)
    superseded_at = models.DateTimeField(null=True, blank=True)
    counts = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "material_edition"
        indexes = [
            models.Index(fields=["work", "-applies_from_ord"], name="mat_ed_work_ord_idx"),
            models.Index(fields=["status", "-updated_at"], name="mat_ed_stat_upd_idx"),
        ]
        constraints = [
            models.UniqueConstraint(fields=["work", "label"], name="uq_mat_edition_work_label"),
        ]

    def __str__(self) -> str:
        return f"{self.work.title} - {self.label} ({self.status})"


class Unit(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    edition = models.ForeignKey(Edition, on_delete=models.CASCADE, related_name="units")
    unit_key = models.CharField(max_length=120)
    module_label = models.CharField(max_length=64, default="", blank=True)
    printed_number = models.CharField(max_length=64, default="", blank=True)
    title = models.CharField(max_length=200)
    page_start = models.SmallIntegerField(null=True, blank=True)
    page_end = models.SmallIntegerField(null=True, blank=True)
    sort_order = models.SmallIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "material_unit"
        indexes = [
            models.Index(fields=["edition", "sort_order"], name="mat_unit_ed_sort_idx"),
        ]
        constraints = [
            models.UniqueConstraint(fields=["edition", "unit_key"], name="uq_mat_unit_edition_key"),
        ]

    def __str__(self) -> str:
        return f"{self.printed_number} {self.title} ({self.unit_key})"


class UnitChapter(models.Model):
    class Status(models.TextChoices):
        SUGGESTED = "suggested", "Suggested"
        CONFIRMED = "confirmed", "Confirmed"
        REJECTED = "rejected", "Rejected"

    class Origin(models.TextChoices):
        EDITOR = "editor", "Editor"
        COPIED = "copied", "Copied"
        REMAP = "remap", "Remap"
        AI = "ai", "AI"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    unit = models.ForeignKey(Unit, on_delete=models.CASCADE, related_name="chapter_mappings")
    chapter_id = models.UUIDField(db_index=True)
    subject_key = models.CharField(max_length=80)
    chapter_key = models.CharField(max_length=120)
    scheme_id = models.UUIDField(db_index=True)
    is_primary = models.BooleanField(default=False)
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.CONFIRMED)
    origin = models.CharField(max_length=32, choices=Origin.choices, default=Origin.EDITOR)
    confidence = models.DecimalField(max_digits=3, decimal_places=2, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "material_unitchapter"
        constraints = [
            models.UniqueConstraint(fields=["unit", "chapter_id"], name="uq_mat_unitchapter_unit_ch"),
        ]

    def __str__(self) -> str:
        return f"UnitChapter({self.unit_id} -> {self.chapter_key}, primary={self.is_primary})"


class Item(models.Model):
    class Kind(models.TextChoices):
        ILLUSTRATION = "illustration", "Illustration"
        EXAMPLE = "example", "Example"
        EXERCISE = "exercise", "Exercise"
        MCQ = "mcq", "MCQ"
        TRUE_FALSE = "true_false", "True/False"
        THEORY = "theory", "Theory"
        PRACTICAL = "practical", "Practical"
        CASE_STUDY = "case_study", "Case Study"

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        RETIRED = "retired", "Retired"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    work = models.ForeignKey(Work, on_delete=models.RESTRICT, related_name="items")
    item_key = models.CharField(max_length=80)
    kind = models.CharField(max_length=32, choices=Kind.choices)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.ACTIVE)
    first_edition = models.ForeignKey(Edition, on_delete=models.RESTRICT, related_name="introduced_items")
    last_edition = models.ForeignKey(
        Edition, null=True, blank=True, on_delete=models.SET_NULL, related_name="retired_items"
    )
    question_id = models.UUIDField(null=True, blank=True, unique=True)
    canonical_key = models.CharField(max_length=120, null=True, blank=True, db_index=True)
    created_by = models.UUIDField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "material_item"
        indexes = [
            models.Index(fields=["work", "status"], name="mat_item_work_stat_idx"),
        ]
        constraints = [
            models.UniqueConstraint(fields=["work", "item_key"], name="uq_mat_item_work_key"),
        ]

    def __str__(self) -> str:
        return f"Item({self.item_key}, {self.kind})"


class EditionItem(models.Model):
    class MapStatus(models.TextChoices):
        SUGGESTED = "suggested", "Suggested"
        CONFIRMED = "confirmed", "Confirmed"
        REJECTED = "rejected", "Rejected"

    class MapOrigin(models.TextChoices):
        EDITOR = "editor", "Editor"
        COPIED = "copied", "Copied"
        AI = "ai", "AI"
        REMAP = "remap", "Remap"

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        REMOVED = "removed", "Removed"

    class ChangeKind(models.TextChoices):
        SAME = "same", "Same"
        EDITED = "edited", "Edited"
        RENUMBERED = "renumbered", "Renumbered"
        MOVED = "moved", "Moved"
        NEW = "new", "New"
        REMOVED = "removed", "Removed"

    class MatchMethod(models.TextChoices):
        HASH = "hash", "Hash"
        LABEL = "label", "Label"
        ALIGNMENT = "alignment", "Alignment"
        FUZZY = "fuzzy", "Fuzzy"
        MANUAL = "manual", "Manual"
        NEW = "new", "New"

    class MatchStatus(models.TextChoices):
        AUTO = "auto", "Auto"
        NEEDS_REVIEW = "needs_review", "Needs Review"
        CONFIRMED = "confirmed", "Confirmed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    edition = models.ForeignKey(Edition, on_delete=models.CASCADE, related_name="items")
    item = models.ForeignKey(Item, on_delete=models.RESTRICT, related_name="edition_items")
    unit = models.ForeignKey(Unit, on_delete=models.CASCADE, related_name="items")
    printed_label = models.CharField(max_length=60)
    label_norm = models.CharField(max_length=60, db_index=True)
    printed_ordinal = models.IntegerField(null=True, blank=True)
    page_start = models.SmallIntegerField(null=True, blank=True)
    page_end = models.SmallIntegerField(null=True, blank=True)
    position = models.IntegerField()
    descriptor = models.CharField(max_length=140, null=True, blank=True)
    chapter_id = models.UUIDField(db_index=True)
    topic_id = models.UUIDField(null=True, blank=True)
    subject_key = models.CharField(max_length=80)
    chapter_key = models.CharField(max_length=120)
    map_status = models.CharField(max_length=32, choices=MapStatus.choices, default=MapStatus.CONFIRMED)
    map_origin = models.CharField(max_length=32, choices=MapOrigin.choices, default=MapOrigin.EDITOR)
    map_confidence = models.DecimalField(max_digits=3, decimal_places=2, null=True, blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.ACTIVE)
    change_kind = models.CharField(max_length=32, choices=ChangeKind.choices, default=ChangeKind.NEW)
    previous_id = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.SET_NULL, related_name="next_versions"
    )
    match_method = models.CharField(max_length=32, choices=MatchMethod.choices, default=MatchMethod.NEW)
    match_confidence = models.DecimalField(max_digits=3, decimal_places=2, null=True, blank=True)
    match_status = models.CharField(max_length=32, choices=MatchStatus.choices, default=MatchStatus.CONFIRMED)
    match_hash = models.CharField(max_length=64, null=True, blank=True, db_index=True)
    simhash = models.BigIntegerField(null=True, blank=True)
    question_version_id = models.UUIDField(null=True, blank=True)
    version = models.IntegerField(default=1)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "material_editionitem"
        indexes = [
            models.Index(fields=["edition", "chapter_id", "position"], name="mat_editem_ed_ch_pos_idx"),
            models.Index(fields=["item", "edition"], name="mat_editem_it_ed_idx"),
            models.Index(fields=["edition", "unit", "position"], name="mat_editem_ed_unit_pos_idx"),
        ]
        constraints = [
            models.UniqueConstraint(fields=["edition", "item"], name="uq_mat_editem_edition_item"),
        ]

    def __str__(self) -> str:
        return f"{self.printed_label} (Edition: {self.edition_id})"


class Progress(models.Model):
    class State(models.TextChoices):
        DONE = "done", "Done"
        REVISE = "revise", "Revise"
        SKIPPED = "skipped", "Skipped"

    user_id = models.UUIDField(db_index=True)
    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name="user_progress")
    state = models.CharField(max_length=16, choices=State.choices)
    note = models.TextField(default="", blank=True)
    done_at = models.DateTimeField(null=True, blank=True)
    edition = models.ForeignKey(Edition, on_delete=models.RESTRICT, related_name="progress_marks")
    content_stamp = models.CharField(max_length=64, null=True, blank=True)
    self_declared = models.BooleanField(default=False)
    revisited_at = models.DateTimeField(null=True, blank=True)
    client_ts = models.DateTimeField()

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "material_progress"
        constraints = [
            models.UniqueConstraint(fields=["user_id", "item"], name="uq_mat_progress_user_item"),
        ]
        indexes = [
            models.Index(fields=["user_id", "state", "-updated_at"], name="mat_prog_usr_stat_idx"),
            models.Index(fields=["user_id", "edition"], name="mat_prog_usr_ed_idx"),
        ]

    def __str__(self) -> str:
        return f"Progress({self.user_id}, {self.item_id}: {self.state})"


class UserProvider(models.Model):
    class Relation(models.TextChoices):
        FOLLOWS = "follows", "Follows"
        BOUGHT_COURSE = "bought_course", "Bought Course"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user_id = models.UUIDField(db_index=True)
    provider = models.ForeignKey(Provider, on_delete=models.RESTRICT, related_name="followers")
    relation = models.CharField(max_length=32, choices=Relation.choices, default=Relation.FOLLOWS)
    course_title = models.CharField(max_length=120, default="", blank=True)
    batch_label = models.CharField(max_length=60, default="", blank=True)
    purchased_on = models.DateField(null=True, blank=True)
    valid_until = models.DateField(null=True, blank=True)
    subject_keys = models.JSONField(default=list, blank=True)
    created_via = models.CharField(max_length=32, default="settings")
    entitlement_source = models.CharField(max_length=64, null=True, blank=True)
    archived_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "material_userprovider"
        indexes = [
            models.Index(fields=["user_id"], name="mat_uprov_usr_idx"),
            models.Index(fields=["provider"], name="mat_uprov_prov_idx"),
        ]

    def __str__(self) -> str:
        return f"UserProvider({self.user_id} -> {self.provider.slug}: {self.relation})"


class UserEdition(models.Model):
    user_id = models.UUIDField(db_index=True)
    work = models.ForeignKey(Work, on_delete=models.CASCADE, related_name="user_selections")
    edition = models.ForeignKey(
        Edition, null=True, blank=True, on_delete=models.SET_NULL, related_name="user_followers"
    )
    banner_dismissed_for_edition_id = models.UUIDField(null=True, blank=True)
    banner_dismissed_until = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "material_useredition"
        constraints = [
            models.UniqueConstraint(fields=["user_id", "work"], name="uq_mat_useredition_user_work"),
        ]
        indexes = [
            models.Index(fields=["work", "edition"], name="mat_ued_work_ed_idx"),
        ]

    def __str__(self) -> str:
        return f"UserEdition({self.user_id}, work={self.work_id}, edition={self.edition_id})"


class Report(models.Model):
    class Kind(models.TextChoices):
        WRONG_PAGE = "wrong_page", "Wrong Page"
        WRONG_CHAPTER = "wrong_chapter", "Wrong Chapter"
        WRONG_LABEL = "wrong_label", "Wrong Label"
        LINK_DEAD = "link_dead", "Link Dead"
        COPYRIGHT = "copyright", "Copyright"
        OTHER = "other", "Other"

    class Status(models.TextChoices):
        OPEN = "open", "Open"
        ACCEPTED = "accepted", "Accepted"
        REJECTED = "rejected", "Rejected"
        FIXED = "fixed", "Fixed"
        DUPLICATE = "duplicate", "Duplicate"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name="reports")
    edition = models.ForeignKey(Edition, on_delete=models.CASCADE, related_name="reports")
    reporter_user_id = models.UUIDField(db_index=True)
    kind = models.CharField(max_length=32, choices=Kind.choices)
    message = models.TextField(max_length=500, default="", blank=True)
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.OPEN)
    resolved_by = models.UUIDField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolution_note = models.TextField(default="", blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "material_report"
        indexes = [
            models.Index(fields=["status", "created_at"], name="mat_rep_stat_crt_idx"),
            models.Index(fields=["item", "status"], name="mat_rep_item_stat_idx"),
        ]

    def __str__(self) -> str:
        return f"Report({self.id}, {self.kind}, status={self.status})"


class ImportJob(models.Model):
    class Status(models.TextChoices):
        UPLOADED = "uploaded", "Uploaded"
        VALIDATING = "validating", "Validating"
        NEEDS_FIXES = "needs_fixes", "Needs Fixes"
        IMPORTED = "imported", "Imported"
        FAILED = "failed", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    edition = models.ForeignKey(Edition, on_delete=models.CASCADE, related_name="import_jobs")
    user_id = models.UUIDField()
    format = models.CharField(max_length=16, default="csv")
    attachment_id = models.UUIDField(null=True, blank=True)
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.UPLOADED)
    counts = models.JSONField(default=dict, blank=True)
    error_attachment_id = models.UUIDField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "material_importjob"

    def __str__(self) -> str:
        return f"ImportJob({self.id}, {self.format}, status={self.status})"


class AuditLog(models.Model):
    id = models.BigAutoField(primary_key=True)
    actor_id = models.UUIDField(null=True, blank=True)
    entity_type = models.CharField(max_length=64)
    entity_id = models.UUIDField(db_index=True)
    action = models.CharField(max_length=64)
    before = models.JSONField(default=dict, blank=True)
    after = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "material_auditlog"
        indexes = [
            models.Index(fields=["entity_type", "entity_id", "-created_at"], name="mat_audit_ent_idx"),
        ]

    def __str__(self) -> str:
        return f"MaterialAuditLog({self.action} on {self.entity_type}:{self.entity_id})"
