"""Read-only support views over the Pomodoro timer. Support never edits a student's timer or settings."""

from django.contrib import admin

from modules.profiles.models import Profile

from .models import ActiveTimer, FocusSettings


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


@admin.register(ActiveTimer)
class ActiveTimerAdmin(ReadOnlyAdmin):
    list_display = ("student", "phase", "round_number", "started_at", "away_pending")
    list_filter = ("phase", "away_pending")
    search_fields = ("user_id",)

    @admin.display(description="Student")
    def student(self, obj):
        return _email(obj.user_id)


@admin.register(FocusSettings)
class FocusSettingsAdmin(ReadOnlyAdmin):
    list_display = ("student", "last_preset", "auto_start_breaks", "auto_start_focus", "sound_enabled")
    search_fields = ("user_id",)

    @admin.display(description="Student")
    def student(self, obj):
        return _email(obj.user_id)
