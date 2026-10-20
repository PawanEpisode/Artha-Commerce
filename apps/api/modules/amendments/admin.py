from __future__ import annotations

from django.contrib import admin

from .models import (
    Amendment,
    AmendmentAuditLog,
    CardState,
    Change,
    ChangeMap,
    ChangeVersion,
    Revision,
    RevisionSubject,
    RevisionTerm,
)


class RevisionSubjectInline(admin.TabularInline):
    model = RevisionSubject
    extra = 0
    raw_id_fields = ("subject", "scheme", "level")


class RevisionTermInline(admin.TabularInline):
    model = RevisionTerm
    extra = 0
    raw_id_fields = ("exam_term",)


class ChangeMapInline(admin.TabularInline):
    model = ChangeMap
    extra = 0
    raw_id_fields = ("subject", "chapter", "topic", "scheme")


@admin.register(Amendment)
class AmendmentAdmin(admin.ModelAdmin):
    list_display = (
        "public_id",
        "short_title",
        "doc_key",
        "kind",
        "course",
        "level",
        "status",
        "live_revision",
        "last_released_at",
    )
    list_filter = ("status", "kind", "course", "level")
    search_fields = ("public_id", "slug", "title", "short_title", "doc_key")
    readonly_fields = ("public_id", "created_at", "updated_at")


@admin.register(Revision)
class RevisionAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "amendment",
        "revision_no",
        "state",
        "revision_kind",
        "issued_on",
        "released_at",
    )
    list_filter = ("state", "revision_kind")
    search_fields = ("amendment__title", "amendment__slug", "doc_sha256")
    inlines = [RevisionSubjectInline, RevisionTermInline]
    readonly_fields = ("created_at", "updated_at")


@admin.register(Change)
class ChangeAdmin(admin.ModelAdmin):
    list_display = (
        "public_id",
        "card_key",
        "amendment",
        "status",
        "needs_attention",
        "live_version",
    )
    list_filter = ("status", "needs_attention")
    search_fields = ("public_id", "card_key", "amendment__title")
    readonly_fields = ("public_id", "created_at", "updated_at")


@admin.register(ChangeVersion)
class ChangeVersionAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "change",
        "provision_label",
        "title",
        "change_type",
        "materiality",
        "revision_effect",
        "is_live",
    )
    list_filter = ("change_type", "materiality", "revision_effect", "is_live")
    search_fields = ("provision_label", "title", "summary_new", "law_key")
    inlines = [ChangeMapInline]
    readonly_fields = ("created_at",)


@admin.register(CardState)
class CardStateAdmin(admin.ModelAdmin):
    list_display = ("user_id", "change", "reviewed_at", "saved")
    list_filter = ("saved",)
    search_fields = ("user_id", "change__card_key")
    readonly_fields = ("first_seen_at", "updated_at")


@admin.register(AmendmentAuditLog)
class AmendmentAuditLogAdmin(admin.ModelAdmin):
    list_display = ("amendment", "revision", "change", "action", "actor_id", "created_at")
    list_filter = ("action",)
    search_fields = ("amendment__public_id", "action")
    readonly_fields = ("created_at",)
