"""
Django Admin for F-08 Mock Tests.
"""

from __future__ import annotations

from django.contrib import admin
from .models import (
    Attempt,
    AttemptSection,
    ChoiceGroup,
    ExamFormat,
    Item,
    Paper,
    PaperReview,
    PaperVersion,
    Section,
    Series,
    Settings,
)


@admin.register(Series)
class SeriesAdmin(admin.ModelAdmin):
    list_display = ("title", "course", "level", "kind", "status", "series_no")
    list_filter = ("course", "level", "kind", "status")
    search_fields = ("title", "slug")


class SectionInline(admin.TabularInline):
    model = Section
    extra = 0


class ItemInline(admin.TabularInline):
    model = Item
    extra = 0
    raw_id_fields = ("question",)


@admin.register(PaperVersion)
class PaperVersionAdmin(admin.ModelAdmin):
    list_display = ("paper", "version_no", "state", "total_marks", "duration_seconds", "published_at")
    list_filter = ("state",)
    inlines = [SectionInline, ItemInline]


@admin.register(Paper)
class PaperAdmin(admin.ModelAdmin):
    list_display = ("title", "public_id", "course", "level", "kind", "source_tag", "status", "visibility")
    list_filter = ("course", "level", "kind", "source_tag", "status", "visibility")
    search_fields = ("title", "public_id", "slug")


@admin.register(ExamFormat)
class ExamFormatAdmin(admin.ModelAdmin):
    list_display = ("name", "course", "level", "subject_key", "total_marks", "duration_seconds", "verified")
    list_filter = ("course", "level", "verified", "status")


@admin.register(Attempt)
class AttemptAdmin(admin.ModelAdmin):
    list_display = ("paper", "user_id", "attempt_no", "run_mode", "phase", "score", "percent", "completed_at")
    list_filter = ("run_mode", "phase")
    search_fields = ("user_id", "session_id")
