from django.contrib import admin

from .models import Profile


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    """Support view of students. Only the role (student, editor, admin) can be changed, and only by superusers."""

    list_display = ("email", "full_name", "course", "level", "role", "created_at")
    list_filter = ("role", "course")
    search_fields = ("email", "full_name", "id")
    ordering = ("-created_at",)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_readonly_fields(self, request, obj=None):
        fields = [f.name for f in Profile._meta.fields if f.name != "role"]
        return fields if request.user.is_superuser else [*fields, "role"]
