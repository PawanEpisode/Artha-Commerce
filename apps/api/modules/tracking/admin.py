"""
Read-only support views over students' tracked time. Nothing here edits a session: students correct their own time in the
app. The one write is "rebuild", which recomputes the derived roll-ups from the sessions and is always safe to repeat.
"""

from django.contrib import admin, messages

from modules.profiles.models import Profile

from . import rollups
from .models import SessionAudit, StudySession


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


@admin.register(StudySession)
class StudySessionAdmin(ReadOnlyAdmin):
    list_display = ("student", "study_date", "source", "minutes", "subject", "is_edited", "overlaps_other")
    list_filter = ("source", "is_edited", "overlaps_other")
    search_fields = ("user_id",)
    date_hierarchy = "study_date"
    list_select_related = ("subject",)
    exclude = ("note",)  # notes are personal; support never needs them
    actions = ["rebuild"]

    @admin.display(description="Student")
    def student(self, obj):
        return _email(obj.user_id)

    @admin.display(description="Minutes")
    def minutes(self, obj):
        return round(obj.focus_seconds / 60, 1)

    @admin.action(description="Rebuild roll-ups for the selected students (superusers)")
    def rebuild(self, request, queryset):
        if not request.user.is_superuser:
            self.message_user(request, "Only superusers can rebuild.", messages.ERROR)
            return
        users = set(queryset.values_list("user_id", flat=True))
        days = sum(rollups.rebuild(user) for user in users)
        self.message_user(request, f"Rebuilt {days} day(s) for {len(users)} student(s).", messages.SUCCESS)


@admin.register(SessionAudit)
class SessionAuditAdmin(ReadOnlyAdmin):
    list_display = ("student", "action", "session_count", "created_at")
    list_filter = ("action",)
    exclude = ("snapshot",)

    @admin.display(description="Student")
    def student(self, obj):
        return _email(obj.user_id)
