"""
Read-only support views over students' coverage data. Nothing here edits progress: the ledger is the source of truth.
The one write is "rebuild", which replays the ledger and is always safe to repeat.
"""

from django.contrib import admin, messages

from modules.profiles.models import Profile

from . import services
from .models import CoverageEvent, Enrollment


class ReadOnlyAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


def _email(user_id) -> str:
    profile = Profile.objects.filter(pk=user_id).only("email").first()
    return profile.email if profile and profile.email else str(user_id)


@admin.register(Enrollment)
class EnrollmentAdmin(ReadOnlyAdmin):
    list_display = ("student", "level", "scheme", "status", "target_term", "created_at")
    list_filter = ("status", "level__course", "level", "scheme")
    search_fields = ("user_id",)
    list_select_related = ("level", "level__course", "scheme", "target_term")
    actions = ["rebuild"]

    @admin.display(description="Student")
    def student(self, obj):
        return _email(obj.user_id)

    @admin.action(description="Rebuild progress from the ledger (safe to repeat)", permissions=["change_progress"])
    def rebuild(self, request, queryset):
        for enrollment in queryset:
            services.rebuild_enrollment(enrollment)
        self.message_user(request, f"Rebuilt {queryset.count()} enrolments.", messages.SUCCESS)

    def has_change_progress_permission(self, request):
        return request.user.is_superuser


@admin.register(CoverageEvent)
class CoverageEventAdmin(ReadOnlyAdmin):
    list_display = ("occurred_at", "student", "type", "chapter", "value", "source")
    list_filter = ("type", "source")
    list_select_related = ("chapter",)
    date_hierarchy = "occurred_at"

    @admin.display(description="Student")
    def student(self, obj):
        return _email(obj.user_id)
