"""Quota plans are edited here by an admin (PRD 8.5); everything a student writes is read-only for support."""

from django.contrib import admin

from core.admin_base import ReadOnlyAdmin

from .models import Note, QuotaPlan, QuotaUsage


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
