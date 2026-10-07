"""Quota plans are edited here by an admin (PRD 8.5); everything a student writes is read-only for support."""

from django.contrib import admin

from core.admin_base import ReadOnlyAdmin

from .models import Annotation, Document, DocumentChapter, ExportJob, FileContent, Note, QuotaPlan, QuotaUsage


@admin.register(QuotaPlan)
class QuotaPlanAdmin(admin.ModelAdmin):
    list_display = (
        "plan_code",
        "max_notes",
        "max_storage_mb",
        "max_tags",
        "ai_summaries_per_month",
        "exports_per_month",
    )


@admin.register(QuotaUsage)
class QuotaUsageAdmin(ReadOnlyAdmin):
    list_display = ("user_id", "notes_active", "tags_count", "bytes_used", "reconciled_at")


@admin.register(Note)
class NoteAdmin(ReadOnlyAdmin):
    """Metadata only. The text of a note is the student's; support does not browse it."""

    list_display = ("id", "user_id", "kind", "rev", "updated_at", "deleted_at")
    fields = ("id", "user_id", "kind", "rev", "created_at", "updated_at", "deleted_at")


@admin.register(Document)
class DocumentAdmin(ReadOnlyAdmin):
    """Status and sizes only. Titles and file names are the student's own words; support does not browse them."""

    list_display = ("id", "user_id", "origin", "status", "status_reason", "bytes", "page_count", "rev", "deleted_at")
    list_filter = ("status", "origin")
    actions = ("rerun_inspection",)

    @admin.action(description="Run the inspection again (failed or stuck documents)")
    def rerun_inspection(self, request, queryset):
        """Support tool: a `failed` or long-`inspecting` document goes back to the worker. Never reads or changes the student's text."""
        from core import jobs

        from .jobs import JOB_INSPECT

        stuck = queryset.filter(status__in=[Document.Status.FAILED, Document.Status.INSPECTING])
        ids = list(stuck.values_list("id", flat=True))
        stuck.update(status=Document.Status.INSPECTING, status_reason=None)
        for document_id in ids:
            jobs.enqueue(JOB_INSPECT, {"document_id": str(document_id)}, dedupe_key=f"{JOB_INSPECT}:{document_id}")
        self.message_user(request, f"Queued {len(ids)} inspection(s).")

    fields = (
        "id",
        "user_id",
        "origin",
        "status",
        "status_reason",
        "source_kind",
        "bytes",
        "page_count",
        "ocr_mode",
        "marks_count",
        "change_seq",
        "rev",
        "created_at",
        "updated_at",
        "deleted_at",
        "purge_after",
    )


@admin.register(FileContent)
class FileContentAdmin(ReadOnlyAdmin):
    list_display = (
        "id",
        "bytes",
        "page_count",
        "is_encrypted",
        "is_scanned",
        "text_status",
        "ocr_status",
        "orphaned_at",
    )
    list_filter = ("text_status", "ocr_status")
    exclude = ("page_meta", "outline")  # derived from the student's file: not browsed


@admin.register(Annotation)
class AnnotationAdmin(ReadOnlyAdmin):
    """Counts and kinds only. The quote, the comment and the geometry are the student's reading and are never shown."""

    list_display = ("id", "user_id", "document_id", "page", "kind", "rev", "seq", "deleted_at")
    list_filter = ("kind",)
    fields = ("id", "user_id", "document_id", "page", "kind", "rev", "seq", "created_at", "updated_at", "deleted_at")


@admin.register(DocumentChapter)
class DocumentChapterAdmin(ReadOnlyAdmin):
    list_display = ("id", "user_id", "document_id", "page_from", "page_to", "source")


@admin.register(ExportJob)
class ExportJobAdmin(ReadOnlyAdmin):
    list_display = ("id", "user_id", "kind", "status", "progress", "error_code", "expires_at", "created_at")
    list_filter = ("status", "kind")
    fields = ("id", "user_id", "kind", "status", "progress", "page_count", "error_code", "expires_at", "created_at")
