"""
Django admin configuration for PYQ (papers, choice groups, questions tree, links).
"""

from __future__ import annotations

from django.contrib import admin

from .models import AskedCache, ChoiceGroup, DailySet, PaperLink, PaperQuestion, PyqPaper


class ChoiceGroupInline(admin.TabularInline):
    model = ChoiceGroup
    extra = 0


class PaperLinkInline(admin.TabularInline):
    model = PaperLink
    extra = 0


class PaperQuestionInline(admin.TabularInline):
    model = PaperQuestion
    extra = 0
    raw_id_fields = ("question", "chapter", "parent")


@admin.register(PyqPaper)
class PyqPaperAdmin(admin.ModelAdmin):
    list_display = (
        "external_ref",
        "title",
        "term_code",
        "subject_key",
        "delivery",
        "answers_status",
        "status",
        "question_count",
    )
    list_filter = ("status", "delivery", "answers_status", "syllabus_status", "course", "level")
    search_fields = ("external_ref", "title", "subject_key", "term_code")
    inlines = [ChoiceGroupInline, PaperLinkInline, PaperQuestionInline]


@admin.register(AskedCache)
class AskedCacheAdmin(admin.ModelAdmin):
    list_display = ("question", "asked_n", "window_n", "last_term_code", "refreshed_at")
    search_fields = ("question__public_id", "last_term_code")


@admin.register(DailySet)
class DailySetAdmin(admin.ModelAdmin):
    list_display = ("level", "local_date", "status", "pool_size", "item_count")
    list_filter = ("status", "level")
