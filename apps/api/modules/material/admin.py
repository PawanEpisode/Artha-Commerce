"""
Django admin registrations for F-12 Institute Study Material.
"""

from __future__ import annotations

from django.contrib import admin

from .models import (
    AuditLog,
    Edition,
    EditionItem,
    ImportJob,
    Item,
    Progress,
    Provider,
    Report,
    Unit,
    UnitChapter,
    UserEdition,
    UserProvider,
    Work,
)


@admin.register(Provider)
class ProviderAdmin(admin.ModelAdmin):
    list_display = ("slug", "name", "kind", "status", "created_at")
    list_filter = ("kind", "status")
    search_fields = ("name", "slug", "normalised_name")


@admin.register(Work)
class WorkAdmin(admin.ModelAdmin):
    list_display = ("work_key", "title", "provider", "subject_key", "kind", "visibility", "status")
    list_filter = ("kind", "visibility", "status", "provider")
    search_fields = ("work_key", "title", "subject_key")


@admin.register(Edition)
class EditionAdmin(admin.ModelAdmin):
    list_display = ("label", "work", "applies_from_term", "status", "published_at")
    list_filter = ("status", "work")
    search_fields = ("label", "work__title")


@admin.register(Unit)
class UnitAdmin(admin.ModelAdmin):
    list_display = ("unit_key", "edition", "title", "sort_order")
    list_filter = ("edition",)
    search_fields = ("unit_key", "title")


@admin.register(UnitChapter)
class UnitChapterAdmin(admin.ModelAdmin):
    list_display = ("unit", "chapter_key", "is_primary", "status", "origin")
    list_filter = ("is_primary", "status", "origin")


@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    list_display = ("item_key", "work", "kind", "status", "created_at")
    list_filter = ("kind", "status", "work")
    search_fields = ("item_key",)


@admin.register(EditionItem)
class EditionItemAdmin(admin.ModelAdmin):
    list_display = ("printed_label", "edition", "unit", "chapter_key", "change_kind", "status")
    list_filter = ("change_kind", "status", "map_status")
    search_fields = ("printed_label", "descriptor")


@admin.register(Progress)
class ProgressAdmin(admin.ModelAdmin):
    list_display = ("user_id", "item", "edition", "state", "self_declared", "updated_at")
    list_filter = ("state", "self_declared")
    search_fields = ("user_id",)


@admin.register(UserProvider)
class UserProviderAdmin(admin.ModelAdmin):
    list_display = ("user_id", "provider", "relation", "course_title", "purchased_on")
    list_filter = ("relation", "provider")


@admin.register(UserEdition)
class UserEditionAdmin(admin.ModelAdmin):
    list_display = ("user_id", "work", "edition", "banner_dismissed_until")


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ("kind", "status", "reporter_user_id", "item", "created_at")
    list_filter = ("kind", "status")


@admin.register(ImportJob)
class ImportJobAdmin(admin.ModelAdmin):
    list_display = ("id", "edition", "format", "status", "finished_at")
    list_filter = ("status", "format")


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("action", "entity_type", "entity_id", "actor_id", "created_at")
    list_filter = ("action", "entity_type")
    readonly_fields = ("created_at",)
