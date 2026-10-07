"""
Tables for Smart Notes (F-03). Release R1 owns typed notes, their versions and images, tags and the student's quota and
settings. Documents, PDF marks, AI jobs and shares arrive with R2 and R3 as additive migrations (ERD sections 2.1 to 2.10).

`user_id` holds the Supabase user id by value (no cross-schema foreign key) and scopes every query. Taxonomy links are real
foreign keys to the syllabus (`restrict`) plus stable copies of the keys, written together by `services.links`: views group
by `(level, subject_key, chapter_key)` so notes follow a syllabus scheme switch. See docs/product/erd/F-03-notes-and-pdf-editor.md.
"""

import uuid

from django.contrib.postgres.search import SearchVectorField
from django.db import models
from django.db.models import Q

from core.models import TimeStampedModel, UUIDModel

from .domain.legend import default_legend


class LinkColumns(models.Model):
    """The taxonomy link shared by notes (and later documents, marks and page ranges). Null `chapter` means Unfiled."""

    level = models.ForeignKey("syllabus.Level", null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    subject = models.ForeignKey("syllabus.Subject", null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    chapter = models.ForeignKey("syllabus.Chapter", null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    topic = models.ForeignKey("syllabus.Topic", null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    subject_key = models.CharField(max_length=80, null=True, blank=True)  # noqa: DJ001 - NULL is Unfiled; "" is not a key
    chapter_key = models.CharField(max_length=100, null=True, blank=True)  # noqa: DJ001 - NULL is Unfiled; "" is not a key
    topic_key = models.CharField(max_length=120, null=True, blank=True)  # noqa: DJ001 - NULL is Unfiled; "" is not a key

    class Meta:
        abstract = True


def link_constraints(prefix: str) -> list[models.CheckConstraint]:
    """
    The two integrity rules every table with link columns repeats (ERD section 2): a chapter implies the stable keys, a
    topic implies a chapter. A function, not an inherited Meta, because constraint names must be unique per table.
    """
    return [
        models.CheckConstraint(
            condition=Q(chapter__isnull=True)
            | Q(level__isnull=False, subject_key__isnull=False, chapter_key__isnull=False),
            name=f"{prefix}_chapter_has_keys",
        ),
        models.CheckConstraint(
            condition=Q(topic__isnull=True) | Q(chapter__isnull=False, topic_key__isnull=False),
            name=f"{prefix}_topic_has_chapter",
        ),
    ]


class QuotaPlan(TimeStampedModel):
    """Limits per plan (PRD 8.5). `free` is seeded; paid plans are rows added by an admin when billing exists."""

    plan_code = models.CharField(max_length=32, primary_key=True)
    max_storage_mb = models.IntegerField()
    max_file_mb = models.IntegerField()
    max_pages = models.IntegerField()
    max_documents = models.IntegerField()
    max_notes = models.IntegerField()
    max_note_chars = models.IntegerField()
    max_note_images = models.IntegerField()
    max_marks_per_document = models.IntegerField()
    max_tags = models.IntegerField()
    ocr_pages_per_month = models.IntegerField()
    ai_ocr_pages_per_month = models.IntegerField()
    ai_summaries_per_month = models.IntegerField()
    exports_per_month = models.IntegerField()
    max_share_links = models.IntegerField()
    max_offline_documents = models.IntegerField()

    class Meta:
        db_table = "notes_quotaplan"

    def __str__(self) -> str:
        return self.plan_code


class QuotaUsage(TimeStampedModel):
    """What a student holds right now. Changed only by conditional UPDATEs (`services.quota`), never read-then-write."""

    user_id = models.UUIDField(primary_key=True)
    bytes_used = models.BigIntegerField(default=0)
    docs_active = models.IntegerField(default=0)
    notes_active = models.IntegerField(default=0)  # notes not in the trash
    tags_count = models.IntegerField(default=0)
    share_links_active = models.IntegerField(default=0)
    reconciled_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "notes_quotausage"
        constraints = [
            models.CheckConstraint(
                condition=Q(bytes_used__gte=0, docs_active__gte=0, notes_active__gte=0, tags_count__gte=0)
                & Q(share_links_active__gte=0),
                name="notes_quotausage_nonnegative",
            )
        ]


class MonthlyUsage(TimeStampedModel):
    """Per-month counters (month = first day of the month in India time), charged with a conditional upsert."""

    user_id = models.UUIDField()
    month = models.DateField()
    pk = models.CompositePrimaryKey("user_id", "month")
    ocr_pages = models.IntegerField(default=0)
    ai_ocr_pages = models.IntegerField(default=0)
    ai_summaries = models.IntegerField(default=0)
    exports = models.IntegerField(default=0)
    uploads = models.IntegerField(default=0)

    class Meta:
        db_table = "notes_monthlyusage"
        constraints = [
            models.CheckConstraint(
                condition=Q(ocr_pages__gte=0, ai_ocr_pages__gte=0, ai_summaries__gte=0)
                & Q(exports__gte=0, uploads__gte=0),
                name="notes_monthlyusage_nonnegative",
            )
        ]


class Settings(TimeStampedModel):
    """One row per student, created on first read. Colour names are the student's own legend, never stored per mark."""

    user_id = models.UUIDField(primary_key=True)
    color_legend = models.JSONField(default=default_legend)
    legend_schema = models.SmallIntegerField(default=1)
    default_color = models.CharField(max_length=2, default="y")
    page_tone = models.CharField(max_length=8, default="original")
    finger_draws = models.BooleanField(default=False)
    ocr_default = models.CharField(max_length=6, default="ask")
    ocr_lang = models.CharField(max_length=8, default="eng")
    ai_consent_version = models.CharField(max_length=32, null=True, blank=True)  # noqa: DJ001 - NULL: never consented
    ai_consent_at = models.DateTimeField(null=True, blank=True)
    ai_consent_withdrawn_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "notes_settings"
        constraints = [
            models.CheckConstraint(
                condition=Q(page_tone__in=["original", "paper", "night"]), name="notes_settings_page_tone_valid"
            ),
            models.CheckConstraint(
                condition=Q(ocr_default__in=["ask", "always", "never"]), name="notes_settings_ocr_default_valid"
            ),
            models.CheckConstraint(condition=Q(ocr_lang__in=["eng", "eng+hin"]), name="notes_settings_ocr_lang_valid"),
            models.CheckConstraint(
                condition=Q(default_color__in=["y", "g", "b", "p", "o"]), name="notes_settings_default_color_valid"
            ),
        ]


class Tag(UUIDModel):
    """A student's own free-form label. Not the curated, moderated question-bank vocabulary (ERD Q-F03-8)."""

    user_id = models.UUIDField()
    name = models.CharField(max_length=30)
    name_norm = models.CharField(max_length=60)  # NFKC, lower case, collapsed spaces: what uniqueness is judged on
    color_key = models.CharField(max_length=8, null=True, blank=True)  # noqa: DJ001 - NULL: no colour chosen

    class Meta:
        db_table = "notes_tag"
        constraints = [
            models.UniqueConstraint(fields=["user_id", "name_norm"], name="notes_tag_user_name_unique"),
            models.UniqueConstraint(fields=["id", "user_id"], name="notes_tag_id_user_unique"),
            models.CheckConstraint(condition=Q(name__regex=r".+"), name="notes_tag_name_not_empty"),
        ]


class Note(LinkColumns, UUIDModel):
    class Kind(models.TextChoices):
        NOTE = "note", "Note"
        EXAM_SUMMARY = "exam_summary", "Exam summary"

    class Origin(models.TextChoices):
        TYPED = "typed", "Typed"
        CLIP = "clip", "Clip"
        AI_SUMMARY = "ai_summary", "AI summary"
        IMPORT = "import", "Import"

    user_id = models.UUIDField()
    client_id = models.UUIDField(null=True, blank=True)  # idempotency of offline creates
    kind = models.CharField(max_length=12, choices=Kind.choices, default=Kind.NOTE)
    origin = models.CharField(max_length=10, choices=Origin.choices, default=Origin.TYPED)
    title = models.CharField(max_length=200, blank=True, default="")
    body_md = models.TextField(
        blank=True, default=""
    )  # canonical: sanitised Markdown with KaTeX (core.richtext, profile note)
    body_text = models.TextField(blank=True, default="")  # derived plain text, for search and snippets
    body_chars = models.IntegerField(default=0)
    lang = models.CharField(max_length=5, default="en")  # en, hi, mixed: picks the search configuration
    # Maintained by `services.search_index` on PostgreSQL; null on SQLite (tests), where search falls back to substring match.
    search_tsv = SearchVectorField(null=True, blank=True, editable=False)
    is_current_summary = models.BooleanField(default=False)
    pinned = models.BooleanField(default=False)
    clip_source = models.JSONField(null=True, blank=True)  # {module, ref, label}
    clip_schema = models.SmallIntegerField(default=1)
    # R3 and F-15 columns, nullable and unused in R1, so the busiest table is not altered later.
    ai_job_id = models.UUIDField(null=True, blank=True)
    source_refs = models.JSONField(null=True, blank=True)
    refs_schema = models.SmallIntegerField(default=1)
    recall_card_id = models.UUIDField(null=True, blank=True)
    rev = models.IntegerField(default=1)  # increments on every accepted change, trash and restore included
    deleted_at = models.DateTimeField(null=True, blank=True)
    purge_after = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "notes_note"
        constraints = [
            *link_constraints("notes_note"),
            models.UniqueConstraint(fields=["id", "user_id"], name="notes_note_id_user_unique"),
            models.UniqueConstraint(
                fields=["user_id", "client_id"],
                condition=Q(client_id__isnull=False),
                name="notes_note_client_id_unique",
            ),
            models.UniqueConstraint(
                fields=["user_id", "level", "subject_key", "chapter_key"],
                condition=Q(kind="exam_summary", is_current_summary=True, deleted_at__isnull=True),
                name="notes_note_one_current_summary",
            ),
            models.CheckConstraint(condition=Q(kind__in=["note", "exam_summary"]), name="notes_note_kind_valid"),
            models.CheckConstraint(
                condition=Q(origin__in=["typed", "clip", "ai_summary", "import"]), name="notes_note_origin_valid"
            ),
            models.CheckConstraint(
                condition=Q(kind="exam_summary") | Q(is_current_summary=False), name="notes_note_summary_flag_kind"
            ),
            models.CheckConstraint(
                condition=Q(body_chars__gte=0, body_chars__lte=100000), name="notes_note_body_chars"
            ),
            models.CheckConstraint(condition=Q(rev__gte=1), name="notes_note_rev_positive"),
            models.CheckConstraint(condition=Q(lang__in=["en", "hi", "mixed"]), name="notes_note_lang_valid"),
            models.CheckConstraint(
                condition=Q(purge_after__isnull=True) | Q(deleted_at__isnull=False), name="notes_note_purge_needs_trash"
            ),
        ]
        indexes = [
            models.Index(
                fields=["user_id", "-updated_at", "id"], condition=Q(deleted_at__isnull=True), name="notes_note_hub_idx"
            ),
            models.Index(
                fields=["user_id", "level", "subject_key", "chapter_key", "-updated_at", "id"],
                condition=Q(deleted_at__isnull=True),
                name="notes_note_chapter_idx",
            ),
            models.Index(
                fields=["user_id", "deleted_at"], condition=Q(deleted_at__isnull=False), name="notes_note_trash_idx"
            ),
            models.Index(
                fields=["user_id"],
                condition=Q(chapter__isnull=True, deleted_at__isnull=True),
                name="notes_note_unfiled_idx",
            ),
            models.Index(fields=["purge_after"], condition=Q(deleted_at__isnull=False), name="notes_note_purge_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.kind} {self.pk}"  # never the title: it is the student's text

    @property
    def is_trashed(self) -> bool:
        return self.deleted_at is not None

    def link_key(self) -> tuple | None:
        """`(level_id, subject_key, chapter_key, chapter_id)` or None when Unfiled: what counts are grouped by."""
        if self.chapter_id is None:
            return None
        return (self.level_id, self.subject_key, self.chapter_key, self.chapter_id)


class NoteVersion(TimeStampedModel):
    """History of a note, one row per saved revision. Autosave bursts update one row in place (`services.versions`)."""

    class Source(models.TextChoices):
        AUTOSAVE = "autosave", "Autosave"
        MANUAL = "manual", "Manual"
        RESTORE = "restore", "Restore"
        MERGE = "merge", "Merge"
        AI = "ai", "AI"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    note = models.ForeignKey(Note, on_delete=models.CASCADE, related_name="versions")
    user_id = models.UUIDField()
    rev = models.IntegerField()
    title = models.CharField(max_length=200, blank=True, default="")
    body_md = models.TextField(blank=True, default="")
    source = models.CharField(max_length=10, choices=Source.choices, default=Source.AUTOSAVE)

    class Meta:
        db_table = "notes_noteversion"
        constraints = [
            models.UniqueConstraint(fields=["note", "rev"], name="notes_noteversion_note_rev_unique"),
            models.CheckConstraint(
                condition=Q(source__in=["autosave", "manual", "restore", "merge", "ai"]),
                name="notes_noteversion_source_valid",
            ),
        ]
        indexes = [
            models.Index(fields=["note", "-created_at"], name="notes_noteversion_note_idx"),
            models.Index(fields=["created_at"], name="notes_noteversion_thin_idx"),
        ]


class NoteImage(models.Model):
    """The uploaded images a note's body references, computed on every save. Drives quota and purge."""

    note = models.ForeignKey(Note, on_delete=models.CASCADE, related_name="images")
    attachment = models.ForeignKey("media.Attachment", on_delete=models.CASCADE, related_name="+")
    pk = models.CompositePrimaryKey("note_id", "attachment_id")
    user_id = models.UUIDField()
    alt_text = models.TextField(
        blank=True, default=""
    )  # copied from the Markdown, so "images missing alt" is one query

    class Meta:
        db_table = "notes_noteimage"
        indexes = [models.Index(fields=["attachment"], name="notes_noteimage_attachment_idx")]

    def __str__(self) -> str:
        return f"image of note {self.note_id}"


class ItemTag(UUIDModel):
    """
    A tag on an item. The ERD pattern is three nullable foreign keys (note, annotation, document) with exactly one set, so
    the database enforces integrity instead of a polymorphic by-value id. R1 has only notes: `note` is the single target
    and the check below says so. R2's migration adds `annotation` and `document`, replaces this check with
    `num_nonnulls(note, annotation, document) = 1` and adds their partial unique indexes (ERD 2.8).
    """

    user_id = models.UUIDField()
    tag = models.ForeignKey(Tag, on_delete=models.CASCADE, related_name="items")
    note = models.ForeignKey(Note, null=True, blank=True, on_delete=models.CASCADE, related_name="item_tags")

    class Meta:
        db_table = "notes_itemtag"
        constraints = [
            models.CheckConstraint(condition=Q(note__isnull=False), name="notes_itemtag_one_target"),
            models.UniqueConstraint(
                fields=["tag", "note"], condition=Q(note__isnull=False), name="notes_itemtag_tag_note_unique"
            ),
        ]
        indexes = [models.Index(fields=["note"], name="notes_itemtag_note_idx")]
