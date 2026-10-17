from django.contrib import admin

from .models import (
    ChapterFact,
    Goal,
    MistakeTag,
    ReadinessProfile,
    ReadinessSnapshot,
    Report,
    SessionRun,
    Settings,
    Share,
    TopicFact,
    UserState,
)


@admin.register(SessionRun)
class SessionRunAdmin(admin.ModelAdmin):
    list_display = ("session_id", "user_id", "state", "origin_module", "local_date", "fact_rows", "refreshed_at")
    list_filter = ("state", "origin_module", "mode")
    search_fields = ("session_id", "user_id")


@admin.register(ChapterFact)
class ChapterFactAdmin(admin.ModelAdmin):
    list_display = ("session_id", "subject_key", "chapter_key", "kind", "difficulty", "answered", "correct", "local_date")
    list_filter = ("subject_key", "kind", "difficulty", "is_repeat")
    search_fields = ("user_id", "subject_key", "chapter_key")


@admin.register(TopicFact)
class TopicFactAdmin(admin.ModelAdmin):
    list_display = ("session_id", "topic_id", "subject_key", "answered", "correct", "local_date")
    list_filter = ("subject_key", "is_repeat")
    search_fields = ("user_id", "subject_key")


@admin.register(MistakeTag)
class MistakeTagAdmin(admin.ModelAdmin):
    list_display = ("session_id", "position", "subject_key", "reason", "local_date")
    list_filter = ("reason", "subject_key")
    search_fields = ("user_id", "subject_key")


@admin.register(UserState)
class UserStateAdmin(admin.ModelAdmin):
    list_display = ("user_id", "facts_version", "last_fact_at", "last_session_at", "backfill_status")
    search_fields = ("user_id",)


@admin.register(ReadinessProfile)
class ReadinessProfileAdmin(admin.ModelAdmin):
    list_display = ("course", "level", "version", "status", "effective_from", "effective_to")
    list_filter = ("status", "course")


@admin.register(ReadinessSnapshot)
class ReadinessSnapshotAdmin(admin.ModelAdmin):
    list_display = ("user_id", "scope", "scope_key", "snapshot_date", "score", "confidence", "state")
    list_filter = ("scope", "state", "confidence")
    search_fields = ("user_id", "scope_key")


@admin.register(Goal)
class GoalAdmin(admin.ModelAdmin):
    list_display = ("user_id", "metric", "period", "target", "effective_from", "effective_to")
    list_filter = ("metric", "period")


@admin.register(Settings)
class SettingsAdmin(admin.ModelAdmin):
    list_display = ("user_id", "target_accuracy", "include_estimated", "default_range", "version")


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ("id", "user_id", "status", "period_kind", "from_date", "to_date", "requested_at")
    list_filter = ("status", "period_kind")


@admin.register(Share)
class ShareAdmin(admin.ModelAdmin):
    list_display = ("id", "user_id", "report", "expires_at", "revoked_at", "view_count", "created_at")
