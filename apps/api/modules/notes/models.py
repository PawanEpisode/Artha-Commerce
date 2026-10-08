"""
Tables for Smart Notes (F-03). Release R1 owns typed notes, their versions and images, tags and the student's quota and
settings. R2 adds documents, derived file content and pages, page ranges, PDF marks and export jobs (migrations 0004 and
0005); AI jobs and shares arrive with R3 as additive migrations (ERD sections 2.1 to 2.10).

Composite foreign keys `(parent_id, user_id)`, the page-range exclusion constraint and the GIN indexes cannot be declared in
Django. They live in migrations 0003 to 0005 as PostgreSQL-only DDL (`core.migration_utils`), next to the single-column
foreign keys Django manages, so the owner check is a database fact on PostgreSQL and a service check on SQLite (quick tests).

`user_id` holds the Supabase user id by value (no cross-schema foreign key) and scopes every query. Taxonomy links are real
foreign keys to the syllabus (`restrict`) plus stable copies of the keys, written together by `services.links`: views group
by `(level, subject_key, chapter_key)` so notes follow a syllabus scheme switch. See docs/product/erd/F-03-notes-and-pdf-editor.md.
"""

import uuid

from django.contrib.postgres.search import SearchVectorField
from django.db import models
from django.db.models import Q
from django.db.models.functions import Cast, Length
from django.db.models.lookups import LessThanOrEqual

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
    the database enforces integrity instead of a polymorphic by-value id (ERD 2.8). The composite foreign keys
    `(tag_id, user_id)`, `(note_id, user_id)`, `(annotation_id, user_id)` and `(document_id, user_id)` (migrations 0003
    and 0005) make a tag crossing students impossible.
    """

    user_id = models.UUIDField()
    tag = models.ForeignKey(Tag, on_delete=models.CASCADE, related_name="items")
    note = models.ForeignKey(Note, null=True, blank=True, on_delete=models.CASCADE, related_name="item_tags")
    annotation = models.ForeignKey(
        "Annotation", null=True, blank=True, on_delete=models.CASCADE, related_name="item_tags"
    )
    document = models.ForeignKey("Document", null=True, blank=True, on_delete=models.CASCADE, related_name="item_tags")

    class Meta:
        db_table = "notes_itemtag"
        constraints = [
            # num_nonnulls(note_id, annotation_id, document_id) = 1, written portably so SQLite enforces it too.
            models.CheckConstraint(
                condition=Q(note__isnull=False, annotation__isnull=True, document__isnull=True)
                | Q(note__isnull=True, annotation__isnull=False, document__isnull=True)
                | Q(note__isnull=True, annotation__isnull=True, document__isnull=False),
                name="notes_itemtag_one_target",
            ),
            models.UniqueConstraint(
                fields=["tag", "note"], condition=Q(note__isnull=False), name="notes_itemtag_tag_note_unique"
            ),
            models.UniqueConstraint(
                fields=["tag", "annotation"],
                condition=Q(annotation__isnull=False),
                name="notes_itemtag_tag_annotation_unique",
            ),
            models.UniqueConstraint(
                fields=["tag", "document"],
                condition=Q(document__isnull=False),
                name="notes_itemtag_tag_document_unique",
            ),
        ]
        indexes = [
            models.Index(fields=["note"], name="notes_itemtag_note_idx"),
            models.Index(fields=["annotation"], name="notes_itemtag_annotation_idx"),
            models.Index(fields=["document"], name="notes_itemtag_document_idx"),
        ]


# --- R2: documents, derived content, marks, page ranges, exports (ERD 2.1 to 2.3, 2.6, 2.7, 2.10) -------------------------
class FileContent(UUIDModel):
    """What the worker derives from identical bytes, shared by every document with the same SHA-256 (ERD 2.2)."""

    class TextStatus(models.TextChoices):
        PENDING = "pending", "Pending"
        RUNNING = "running", "Running"
        DONE = "done", "Done"
        FAILED = "failed", "Failed"
        LOCKED = "locked", "Locked"
        SKIPPED = "skipped", "Skipped"

    class OcrStatus(models.TextChoices):
        NONE = "none", "None"
        PENDING = "pending", "Pending"
        RUNNING = "running", "Running"
        PARTIAL = "partial", "Partial"
        DONE = "done", "Done"
        FAILED = "failed", "Failed"

    sha256 = models.CharField(max_length=64, unique=True)
    bytes = models.BigIntegerField()
    page_count = models.IntegerField(null=True, blank=True)  # null while locked
    page_meta = models.JSONField(null=True, blank=True)  # [{w, h}] in points, intrinsic rotation applied
    page_meta_schema = models.SmallIntegerField(default=1)
    outline = models.JSONField(null=True, blank=True)  # tree of {title, page, children}, at most 2,000 nodes
    outline_schema = models.SmallIntegerField(default=1)
    is_encrypted = models.BooleanField(default=False)
    can_copy = models.BooleanField(null=True, blank=True)
    can_modify = models.BooleanField(null=True, blank=True)
    has_javascript = models.BooleanField(default=False)
    is_scanned = models.BooleanField(null=True, blank=True)
    text_pct = models.SmallIntegerField(null=True, blank=True)
    text_status = models.CharField(max_length=8, choices=TextStatus.choices, default=TextStatus.PENDING)
    text_pages_done = models.IntegerField(default=0)  # monotonic: written with greatest()
    ocr_status = models.CharField(max_length=8, choices=OcrStatus.choices, default=OcrStatus.NONE)
    ocr_engine = models.CharField(max_length=40, null=True, blank=True)  # noqa: DJ001 - NULL: never run
    ocr_pages_done = models.IntegerField(default=0)
    ocr_pages_total = models.IntegerField(default=0)
    ocr_avg_conf = models.SmallIntegerField(null=True, blank=True)
    engine_version = models.SmallIntegerField(default=1)
    orphaned_at = models.DateTimeField(null=True, blank=True)  # set when the last referencing document goes

    class Meta:
        db_table = "notes_filecontent"
        constraints = [
            models.CheckConstraint(condition=Q(bytes__gte=0), name="notes_filecontent_bytes"),
            models.CheckConstraint(
                condition=Q(text_status__in=["pending", "running", "done", "failed", "locked", "skipped"]),
                name="notes_filecontent_text_status_valid",
            ),
            models.CheckConstraint(
                condition=Q(ocr_status__in=["none", "pending", "running", "partial", "done", "failed"]),
                name="notes_filecontent_ocr_status_valid",
            ),
            models.CheckConstraint(
                condition=Q(text_pct__isnull=True) | Q(text_pct__gte=0, text_pct__lte=100),
                name="notes_filecontent_text_pct",
            ),
            models.CheckConstraint(
                condition=Q(ocr_avg_conf__isnull=True) | Q(ocr_avg_conf__gte=0, ocr_avg_conf__lte=100),
                name="notes_filecontent_ocr_conf",
            ),
            models.CheckConstraint(
                condition=Q(text_pages_done__gte=0, ocr_pages_done__gte=0, ocr_pages_total__gte=0),
                name="notes_filecontent_progress_nonnegative",
            ),
        ]
        indexes = [
            models.Index(
                fields=["text_status"], condition=Q(text_status__in=["pending", "running"]), name="notes_fc_text_idx"
            ),
            models.Index(
                fields=["ocr_status"],
                condition=Q(ocr_status__in=["pending", "running", "partial"]),
                name="notes_fc_ocr_idx",
            ),
            models.Index(fields=["orphaned_at"], condition=Q(orphaned_at__isnull=False), name="notes_fc_orphan_idx"),
        ]

    def __str__(self) -> str:
        return f"content {self.pk}"


class FilePage(models.Model):
    """One page of a file's text (native, OCR or AI), the search unit of PDFs (ERD 2.3). GIN `(content_id, tsv)` is DDL in 0004."""

    class Source(models.TextChoices):
        NATIVE = "native", "Native"
        OCR = "ocr", "OCR"
        AI = "ai", "AI"

    content = models.ForeignKey(FileContent, on_delete=models.CASCADE, related_name="pages")
    page = models.IntegerField()  # 1-based
    pk = models.CompositePrimaryKey("content_id", "page")
    text = models.TextField(blank=True, default="")  # normalised, at most 60,000 characters
    text_source = models.CharField(max_length=6, choices=Source.choices, default=Source.NATIVE)
    ocr_conf = models.SmallIntegerField(null=True, blank=True)
    words = models.JSONField(null=True, blank=True)  # OCR only: [[x, y, w, h, "word"], ...] in the normalised frame
    words_schema = models.SmallIntegerField(default=1)
    lang = models.CharField(max_length=5, default="en")
    # Maintained by `services.search_index` on PostgreSQL (`english` or `simple` by script); null on SQLite.
    tsv = SearchVectorField(null=True, blank=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "notes_filepage"
        constraints = [
            models.CheckConstraint(condition=Q(page__gte=1), name="notes_filepage_page_positive"),
            models.CheckConstraint(
                condition=Q(text_source__in=["native", "ocr", "ai"]), name="notes_filepage_source_valid"
            ),
            models.CheckConstraint(condition=Q(lang__in=["en", "hi", "mixed"]), name="notes_filepage_lang_valid"),
            models.CheckConstraint(
                condition=Q(ocr_conf__isnull=True) | Q(ocr_conf__gte=0, ocr_conf__lte=100), name="notes_filepage_conf"
            ),
        ]

    def __str__(self) -> str:
        return f"page {self.page} of {self.content_id}"  # never the text


class Document(LinkColumns, UUIDModel):
    """A PDF the student reads and marks (ERD 2.1). `user_id` owns it; platform documents carry `bytes = 0`."""

    class Origin(models.TextChoices):
        UPLOAD = "upload", "Upload"
        PLATFORM = "platform", "Platform"

    class Status(models.TextChoices):
        RESERVED = "reserved", "Reserved"
        SCANNING = "scanning", "Scanning"
        INSPECTING = "inspecting", "Inspecting"
        READY = "ready", "Ready"
        NEEDS_PASSWORD = "needs_password", "Needs password"
        REJECTED = "rejected", "Rejected"
        EXPIRED = "expired", "Expired"
        FAILED = "failed", "Failed"

    class SourceKind(models.TextChoices):
        INSTITUTE_MATERIAL = "institute_material", "Institute material"
        COACHING = "coaching", "Coaching"
        OWN_NOTES = "own_notes", "Own notes"
        HANDWRITTEN = "handwritten", "Handwritten"
        OTHER = "other", "Other"

    ACTIVE_STATUSES = ("reserved", "scanning", "inspecting")

    user_id = models.UUIDField()
    client_id = models.UUIDField(null=True, blank=True)  # idempotency of the reservation
    origin = models.CharField(max_length=8, choices=Origin.choices, default=Origin.UPLOAD)
    title = models.CharField(max_length=200)
    original_filename = models.CharField(max_length=255, blank=True, default="")  # display only, never in a path
    # CASCADE: the attachment row is removed only by notes' own purge (after the document) or by the expiry sweep of an
    # upload that never completed, where the empty reserved document should go with it.
    attachment = models.ForeignKey("media.Attachment", on_delete=models.CASCADE, related_name="+")
    content = models.ForeignKey(FileContent, null=True, blank=True, on_delete=models.PROTECT, related_name="documents")
    cover_attachment = models.ForeignKey(
        "media.Attachment", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    bytes = models.BigIntegerField()  # logical size reserved for quota; 0 for platform documents
    page_count = models.IntegerField(null=True, blank=True)
    status = models.CharField(max_length=14, choices=Status.choices, default=Status.RESERVED)
    status_reason = models.CharField(max_length=20, null=True, blank=True)  # noqa: DJ001 - NULL: no reason
    source_kind = models.CharField(max_length=20, choices=SourceKind.choices, default=SourceKind.OTHER)
    edition_label = models.CharField(max_length=40, null=True, blank=True)  # noqa: DJ001 - NULL: none given
    ocr_mode = models.CharField(max_length=9, default="none")
    ocr_lang = models.CharField(max_length=8, default="eng")
    last_page = models.IntegerField(default=1)
    last_zoom = models.CharField(max_length=8, default="fit")  # "fit" or a percent such as "120"
    page_tone = models.CharField(max_length=8, null=True, blank=True)  # noqa: DJ001 - NULL: follow the setting
    last_opened_at = models.DateTimeField(null=True, blank=True)
    change_seq = models.BigIntegerField(default=0)  # bumped under the row lock on every accepted mark write
    marks_count = models.IntegerField(default=0)  # live marks, same transaction as the write
    reservation_expires_at = models.DateTimeField(null=True, blank=True)
    # R3 Replace edition: this document is the newer edition of `replaces_document_id` (the old one is left as it was).
    replaces_document_id = models.UUIDField(null=True, blank=True)
    reanchor_status = models.CharField(max_length=8, default="none")  # none | waiting | running | done | failed
    reanchor_stats = models.JSONField(null=True, blank=True)  # {total, attached, moved, needs_attention, ranges_copied}
    # R3 Unlock for search: the student's password turned the text of a locked PDF into searchable text (never stored).
    unlock_status = models.CharField(max_length=8, default="none")  # none | waiting | running | done | failed
    unlock_reason = models.CharField(max_length=16, null=True, blank=True)  # noqa: DJ001 - NULL: no failure
    unlock_failures = models.SmallIntegerField(
        default=0
    )  # wrong passwords since the last success, for the attempt limit
    unlock_failed_at = models.DateTimeField(null=True, blank=True)
    # R3 resumable upload: the open multipart upload of a reserved document (cleared when it completes or is aborted).
    resumable_upload_id = models.CharField(max_length=255, null=True, blank=True)  # noqa: DJ001 - NULL: single PUT
    rev = models.IntegerField(default=1)
    deleted_at = models.DateTimeField(null=True, blank=True)
    purge_after = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "notes_document"
        constraints = [
            *link_constraints("notes_document"),
            models.UniqueConstraint(fields=["id", "user_id"], name="notes_document_id_user_unique"),
            models.UniqueConstraint(
                fields=["user_id", "client_id"],
                condition=Q(client_id__isnull=False),
                name="notes_document_client_id_unique",
            ),
            models.CheckConstraint(condition=Q(origin__in=["upload", "platform"]), name="notes_document_origin_valid"),
            models.CheckConstraint(
                condition=Q(reanchor_status__in=["none", "waiting", "running", "done", "failed"]),
                name="notes_document_reanchor_valid",
            ),
            models.CheckConstraint(
                condition=Q(unlock_status__in=["none", "waiting", "running", "done", "failed"]),
                name="notes_document_unlock_valid",
            ),
            models.CheckConstraint(
                condition=Q(
                    status__in=[
                        "reserved",
                        "scanning",
                        "inspecting",
                        "ready",
                        "needs_password",
                        "rejected",
                        "expired",
                        "failed",
                    ]
                ),
                name="notes_document_status_valid",
            ),
            models.CheckConstraint(
                condition=Q(status_reason__isnull=True)
                | Q(
                    status_reason__in=[
                        "type_mismatch",
                        "malware",
                        "pdf_corrupt",
                        "too_many_pages",
                        "too_large",
                        "decode_failed",
                        "policy",
                    ]
                ),
                name="notes_document_reason_valid",
            ),
            models.CheckConstraint(
                condition=Q(source_kind__in=["institute_material", "coaching", "own_notes", "handwritten", "other"]),
                name="notes_document_source_kind_valid",
            ),
            models.CheckConstraint(
                condition=Q(ocr_mode__in=["none", "tesseract", "ai"]), name="notes_document_ocr_mode_valid"
            ),
            models.CheckConstraint(condition=Q(ocr_lang__in=["eng", "eng+hin"]), name="notes_document_ocr_lang_valid"),
            models.CheckConstraint(
                condition=Q(page_tone__isnull=True) | Q(page_tone__in=["original", "paper", "night"]),
                name="notes_document_page_tone_valid",
            ),
            models.CheckConstraint(condition=Q(bytes__gte=0), name="notes_document_bytes_nonnegative"),
            models.CheckConstraint(
                condition=Q(marks_count__gte=0, marks_count__lte=20000), name="notes_document_marks_count"
            ),
            models.CheckConstraint(
                condition=Q(origin="upload") | Q(bytes=0), name="notes_document_platform_has_no_bytes"
            ),
            models.CheckConstraint(condition=Q(rev__gte=1, last_page__gte=1), name="notes_document_rev_page_positive"),
            models.CheckConstraint(
                condition=Q(purge_after__isnull=True) | Q(deleted_at__isnull=False),
                name="notes_document_purge_needs_trash",
            ),
        ]
        indexes = [
            models.Index(fields=["user_id", "deleted_at", "-last_opened_at"], name="notes_document_library_idx"),
            models.Index(
                fields=["user_id", "level", "subject_key", "chapter_key"],
                condition=Q(deleted_at__isnull=True),
                name="notes_document_subject_idx",
            ),
            models.Index(fields=["content"], name="notes_document_content_idx"),
            models.Index(
                fields=["status", "updated_at"],
                condition=Q(status__in=["reserved", "scanning", "inspecting"]),
                name="notes_document_active_idx",
            ),
            models.Index(
                fields=["purge_after"], condition=Q(deleted_at__isnull=False), name="notes_document_purge_idx"
            ),
        ]

    def __str__(self) -> str:
        return f"document {self.pk}"  # never the title or file name: they are the student's text

    @property
    def is_trashed(self) -> bool:
        return self.deleted_at is not None


class DocumentChapter(LinkColumns, UUIDModel):
    """A page range of a document mapped to a chapter (ERD 2.7). Overlaps are refused by an exclusion constraint (DDL in 0004)."""

    class Source(models.TextChoices):
        USER = "user", "User"
        OUTLINE = "outline", "Outline"
        AI = "ai", "AI"

    user_id = models.UUIDField()
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name="ranges")
    page_from = models.IntegerField()
    page_to = models.IntegerField()
    source = models.CharField(max_length=7, choices=Source.choices, default=Source.USER)

    class Meta:
        db_table = "notes_documentchapter"
        constraints = [
            *link_constraints("notes_documentchapter"),
            models.CheckConstraint(
                condition=Q(page_from__gte=1, page_to__gte=models.F("page_from")), name="notes_documentchapter_pages"
            ),
            models.CheckConstraint(condition=Q(chapter__isnull=False), name="notes_documentchapter_chapter_required"),
            models.CheckConstraint(
                condition=Q(source__in=["user", "outline", "ai"]), name="notes_documentchapter_source_valid"
            ),
        ]
        indexes = [models.Index(fields=["document", "page_from"], name="notes_documentchapter_doc_idx")]

    def __str__(self) -> str:
        return f"pages {self.page_from} to {self.page_to}"


class Annotation(LinkColumns, UUIDModel):
    """A mark on a PDF page (ERD 2.6). The id is generated by the client, so an offline create is idempotent."""

    class Kind(models.TextChoices):
        HIGHLIGHT = "highlight", "Highlight"
        UNDERLINE = "underline", "Underline"
        INK = "ink", "Ink"
        TEXTBOX = "textbox", "Text box"
        STICKY = "sticky", "Sticky note"
        BOOKMARK = "bookmark", "Bookmark"
        AREA = "area", "Area"

    class ChapterSource(models.TextChoices):
        EXPLICIT = "explicit", "Explicit"
        RANGE = "range", "Range"
        DOCUMENT = "document", "Document"
        NONE = "none", "None"

    LISTED_KINDS = ("highlight", "underline", "area", "sticky", "textbox")  # marks that carry text or meaning

    user_id = models.UUIDField()
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name="annotations")
    page = models.IntegerField()
    kind = models.CharField(max_length=9, choices=Kind.choices)
    geometry = models.JSONField()  # Geometry v1 (ERD 3.5), at most 64 KB
    geometry_schema = models.SmallIntegerField(default=1)
    color = models.CharField(max_length=2, null=True, blank=True)  # noqa: DJ001 - NULL: no colour (bookmark, text)
    comment = models.TextField(blank=True, default="")
    quote_exact = models.TextField(null=True, blank=True)  # noqa: DJ001 - NULL: not a text mark
    quote_prefix = models.CharField(max_length=32, null=True, blank=True)  # noqa: DJ001 - NULL: not a text mark
    quote_suffix = models.CharField(max_length=32, null=True, blank=True)  # noqa: DJ001 - NULL: not a text mark
    text_start = models.IntegerField(null=True, blank=True)
    text_end = models.IntegerField(null=True, blank=True)
    anchor_engine = models.CharField(max_length=5, null=True, blank=True)  # noqa: DJ001 - NULL: not anchored to text
    chapter_source = models.CharField(max_length=8, choices=ChapterSource.choices, default=ChapterSource.NONE)
    # From quote and comment; maintained by `services.search_index` on PostgreSQL, null on SQLite.
    search_tsv = SearchVectorField(null=True, blank=True, editable=False)
    recall_card_id = models.UUIDField(null=True, blank=True)
    rev = models.IntegerField(default=1)
    seq = models.BigIntegerField()  # the document's `change_seq` at the last accepted change: the delta feed key
    device_id = models.CharField(max_length=36, null=True, blank=True)  # noqa: DJ001 - NULL: unknown device
    deleted_at = models.DateTimeField(null=True, blank=True)  # a tombstone and the trash in one
    purge_after = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "notes_annotation"
        constraints = [
            *link_constraints("notes_annotation"),
            models.UniqueConstraint(fields=["id", "user_id"], name="notes_annotation_id_user_unique"),
            models.CheckConstraint(condition=Q(page__gte=1, page__lte=5000), name="notes_annotation_page"),
            models.CheckConstraint(
                condition=Q(kind__in=["highlight", "underline", "ink", "textbox", "sticky", "bookmark", "area"]),
                name="notes_annotation_kind_valid",
            ),
            models.CheckConstraint(
                condition=LessThanOrEqual(Length(Cast("geometry", models.TextField())), 65536),
                name="notes_annotation_geometry_size",
            ),
            models.CheckConstraint(
                condition=Q(color__isnull=True) | Q(color__in=["y", "g", "b", "p", "o", "i1", "i2", "i3", "i4", "i5"]),
                name="notes_annotation_color_valid",
            ),
            models.CheckConstraint(
                condition=LessThanOrEqual(Length("comment"), 2000), name="notes_annotation_comment_length"
            ),
            models.CheckConstraint(
                condition=LessThanOrEqual(Length("quote_exact"), 1000),  # NULL passes: not a text mark
                name="notes_annotation_quote_length",
            ),
            models.CheckConstraint(
                condition=Q(anchor_engine__isnull=True) | Q(anchor_engine__in=["pdfjs", "ocr"]),
                name="notes_annotation_anchor_valid",
            ),
            models.CheckConstraint(
                condition=Q(chapter_source__in=["explicit", "range", "document", "none"]),
                name="notes_annotation_chapter_source_valid",
            ),
            models.CheckConstraint(condition=Q(rev__gte=1), name="notes_annotation_rev_positive"),
            models.CheckConstraint(
                condition=Q(purge_after__isnull=True) | Q(deleted_at__isnull=False),
                name="notes_annotation_purge_needs_deleted",
            ),
        ]
        indexes = [
            models.Index(fields=["document", "seq"], name="notes_annotation_delta_idx"),
            models.Index(
                fields=["document", "page"], condition=Q(deleted_at__isnull=True), name="notes_annotation_page_idx"
            ),
            models.Index(
                fields=["user_id", "level", "subject_key", "chapter_key", "-updated_at", "id"],
                condition=Q(deleted_at__isnull=True, kind__in=["highlight", "underline", "area", "sticky", "textbox"]),
                name="notes_annotation_chapter_idx",
            ),
            models.Index(
                fields=["user_id", "deleted_at"],
                condition=Q(deleted_at__isnull=False),
                name="notes_annotation_trash_idx",
            ),
            models.Index(
                fields=["purge_after"], condition=Q(deleted_at__isnull=False), name="notes_annotation_purge_idx"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.kind} mark {self.pk}"  # never the quote or the comment

    def link_key(self) -> tuple | None:
        """`(level_id, subject_key, chapter_key, chapter_id)` or None when Unfiled, like `Note.link_key`."""
        if self.chapter_id is None:
            return None
        return (self.level_id, self.subject_key, self.chapter_key, self.chapter_id)


class ExportJob(UUIDModel):
    """A flattened PDF or a whole-account archive being built by the worker (ERD 2.10). `archive` has no document."""

    class Kind(models.TextChoices):
        PDF = "pdf", "PDF"
        ARCHIVE = "archive", "Archive"

    class Status(models.TextChoices):
        QUEUED = "queued", "Queued"
        RUNNING = "running", "Running"
        DONE = "done", "Done"
        FAILED = "failed", "Failed"
        EXPIRED = "expired", "Expired"

    user_id = models.UUIDField()
    kind = models.CharField(max_length=7, choices=Kind.choices, default=Kind.PDF)
    document = models.ForeignKey(Document, null=True, blank=True, on_delete=models.CASCADE, related_name="exports")
    client_id = models.UUIDField(null=True, blank=True)
    options = models.JSONField(default=dict)
    options_schema = models.SmallIntegerField(default=1)
    status = models.CharField(max_length=7, choices=Status.choices, default=Status.QUEUED)
    progress = models.SmallIntegerField(default=0)
    page_count = models.IntegerField(null=True, blank=True)
    attachment = models.ForeignKey(
        "media.Attachment", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )  # kind `note_export`, retention 7 days
    error_code = models.CharField(max_length=20, null=True, blank=True)  # noqa: DJ001 - NULL: no error
    expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "notes_exportjob"
        constraints = [
            models.UniqueConstraint(
                fields=["user_id", "client_id"],
                condition=Q(client_id__isnull=False),
                name="notes_exportjob_client_id_unique",
            ),
            models.CheckConstraint(condition=Q(kind__in=["pdf", "archive"]), name="notes_exportjob_kind_valid"),
            models.CheckConstraint(
                condition=Q(kind="archive") | Q(document__isnull=False), name="notes_exportjob_pdf_has_document"
            ),
            models.CheckConstraint(
                condition=Q(status__in=["queued", "running", "done", "failed", "expired"]),
                name="notes_exportjob_status_valid",
            ),
            models.CheckConstraint(condition=Q(progress__gte=0, progress__lte=100), name="notes_exportjob_progress"),
            models.CheckConstraint(
                condition=Q(error_code__isnull=True)
                | Q(error_code__in=["export_too_large", "restricted", "locked", "failed"]),
                name="notes_exportjob_error_valid",
            ),
        ]
        indexes = [
            models.Index(fields=["user_id", "-created_at"], name="notes_exportjob_owner_idx"),
            models.Index(
                fields=["status", "updated_at"],
                condition=Q(status__in=["queued", "running"]),
                name="notes_exportjob_active_idx",
            ),
            models.Index(
                fields=["expires_at"], condition=Q(expires_at__isnull=False), name="notes_exportjob_expiry_idx"
            ),
        ]


class AiJob(UUIDModel):
    """
    One paid AI request of a student (ERD 2.9, lifecycle 1.3): an exam summary of a chapter, or an AI read of scanned pages.
    The quota charge happens in the same transaction that creates the row; `charged` says whether it still stands (a failed
    or cancelled job refunds it). `result_md` (and `result_json`, the draft's sources) hold the draft only until it is
    accepted, discarded, withdrawn or expired: the row then keeps numbers and ids, never the student's text.
    """

    class Kind(models.TextChoices):
        EXAM_SUMMARY = "exam_summary", "Exam summary"
        OCR_PAGE_AI = "ocr_page_ai", "AI page reading"

    class Status(models.TextChoices):
        QUEUED = "queued", "Queued"
        RUNNING = "running", "Running"
        READY = "ready", "Ready"
        ACCEPTED = "accepted", "Accepted"
        DISCARDED = "discarded", "Discarded"
        EXPIRED = "expired", "Expired"
        FAILED = "failed", "Failed"
        CANCELLED = "cancelled", "Cancelled"
        BUDGET_BLOCKED = "budget_blocked", "Budget blocked"

    ACTIVE = ("queued", "running")

    user_id = models.UUIDField()
    client_id = models.UUIDField()
    kind = models.CharField(max_length=12, choices=Kind.choices)
    scope = models.JSONField(
        default=dict
    )  # ids only: {chapter_id, include, items: [{kind, id}]} or {document_id, pages}
    scope_schema = models.SmallIntegerField(default=1)
    input_hash = models.CharField(
        max_length=64
    )  # SHA-256 of the canonical inputs, prompt version and model: the cache key
    status = models.CharField(max_length=14, choices=Status.choices, default=Status.QUEUED)
    model = models.CharField(max_length=64, null=True, blank=True)  # noqa: DJ001 - NULL until a model ran
    prompt_version = models.CharField(max_length=32, null=True, blank=True)  # noqa: DJ001 - NULL until a prompt ran
    input_tokens = models.IntegerField(default=0)
    output_tokens = models.IntegerField(default=0)
    cost_paise = models.IntegerField(default=0)
    item_count = models.IntegerField(default=0)
    result_md = models.TextField(null=True, blank=True)  # noqa: DJ001 - NULL: no draft stored (cleared after use)
    result_json = models.JSONField(null=True, blank=True)  # the draft's sources, for the review screen
    result_note_id = models.UUIDField(null=True, blank=True)
    charged = models.BooleanField(default=True)
    error_code = models.CharField(max_length=20, null=True, blank=True)  # noqa: DJ001 - NULL: no error
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "notes_aijob"
        constraints = [
            models.UniqueConstraint(fields=["user_id", "client_id"], name="notes_aijob_client_id_unique"),
            models.UniqueConstraint(fields=["id", "user_id"], name="notes_aijob_id_user_unique"),
            models.CheckConstraint(
                condition=Q(kind__in=["exam_summary", "ocr_page_ai"]), name="notes_aijob_kind_valid"
            ),
            models.CheckConstraint(
                condition=Q(
                    status__in=[
                        "queued",
                        "running",
                        "ready",
                        "accepted",
                        "discarded",
                        "expired",
                        "failed",
                        "cancelled",
                        "budget_blocked",
                    ]
                ),
                name="notes_aijob_status_valid",
            ),
            models.CheckConstraint(
                condition=Q(error_code__isnull=True)
                | Q(
                    error_code__in=[
                        "budget",
                        "model_error",
                        "blocked",
                        "too_little",
                        "consent_withdrawn",
                        "unavailable",
                    ]
                ),
                name="notes_aijob_error_valid",
            ),
            models.CheckConstraint(
                condition=Q(input_tokens__gte=0, output_tokens__gte=0, cost_paise__gte=0, item_count__gte=0),
                name="notes_aijob_nonnegative",
            ),
        ]
        indexes = [
            models.Index(
                fields=["user_id", "kind", "input_hash", "-created_at"],
                condition=Q(status__in=["ready", "accepted"]),
                name="notes_aijob_cache_idx",
            ),
            models.Index(
                fields=["status", "created_at"],
                condition=Q(status__in=["queued", "running"]),
                name="notes_aijob_active_idx",
            ),
            models.Index(fields=["user_id", "-created_at"], name="notes_aijob_owner_idx"),
            models.Index(fields=["expires_at"], condition=Q(status="ready"), name="notes_aijob_expiry_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.kind} {self.pk}"  # never the scope or the draft


class ReanchorItem(UUIDModel):
    """
    A mark of the old edition that did not follow the student to the new one (Replace edition, FR-F03-10): "Needs attention".
    It keeps what the student wrote (quote, comment) so nothing is lost, and what they decide: keep the mark where it was, turn
    it into a note, or dismiss it.
    """

    class Status(models.TextChoices):
        OPEN = "open", "Open"
        KEPT = "kept", "Kept"
        NOTED = "noted", "Saved as a note"
        DISMISSED = "dismissed", "Dismissed"

    REASONS = ("not_found", "low_score", "page_changed", "cannot_compare", "no_page", "invalid")

    user_id = models.UUIDField()
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name="reanchor_items")  # the NEW edition
    source_annotation_id = models.UUIDField()
    kind = models.CharField(max_length=9)
    page = models.IntegerField()  # the page in the OLD edition
    color = models.CharField(max_length=2, null=True, blank=True)  # noqa: DJ001 - NULL: no colour
    quote_exact = models.TextField(null=True, blank=True)  # noqa: DJ001 - NULL: not a text mark
    comment = models.TextField(blank=True, default="")
    geometry = models.JSONField()
    reason = models.CharField(max_length=14)
    status = models.CharField(max_length=9, choices=Status.choices, default=Status.OPEN)
    new_annotation_id = models.UUIDField(null=True, blank=True)
    result_note_id = models.UUIDField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "notes_reanchoritem"
        constraints = [
            models.UniqueConstraint(
                fields=["document", "source_annotation_id"], name="notes_reanchoritem_source_unique"
            ),
            models.CheckConstraint(
                condition=Q(status__in=["open", "kept", "noted", "dismissed"]), name="notes_reanchoritem_status_valid"
            ),
        ]
        indexes = [models.Index(fields=["document", "status", "page"], name="notes_reanchoritem_doc_idx")]
