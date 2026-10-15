"""
Django admin configuration for MCQ Bank models.
"""

from __future__ import annotations

from django.contrib import admin

from .models import ExternalLog, McqSet, PatternProfile, RefSource, TestPreset


@admin.register(McqSet)
class McqSetAdmin(admin.ModelAdmin):
    list_display = ("slug", "title", "set_kind", "delivery", "status", "verified", "sort_order")
    list_filter = ("status", "set_kind", "delivery", "verified", "course", "level")
    search_fields = ("slug", "title", "subject_key", "chapter_key")


@admin.register(PatternProfile)
class PatternProfileAdmin(admin.ModelAdmin):
    list_display = ("subject_key", "format", "mcq_count", "mcq_total_marks", "status", "verified", "effective_from")
    list_filter = ("status", "verified", "format", "course", "level")
    search_fields = ("subject_key",)


@admin.register(TestPreset)
class TestPresetAdmin(admin.ModelAdmin):
    list_display = ("name", "is_system", "kind", "mode", "picker", "use_count", "last_used_at")
    list_filter = ("is_system", "kind", "mode")
    search_fields = ("name", "scope_key")


@admin.register(RefSource)
class RefSourceAdmin(admin.ModelAdmin):
    list_display = ("prefix", "label", "url_kind", "status")
    list_filter = ("status", "url_kind")
    search_fields = ("prefix", "label")


@admin.register(ExternalLog)
class ExternalLogAdmin(admin.ModelAdmin):
    list_display = ("user_id", "set", "taken_on", "score", "max_score", "score_pct")
    list_filter = ("taken_on",)
    search_fields = ("user_id",)
