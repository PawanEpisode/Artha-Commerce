"""
Operator switches and read-only plan metadata (PRD section 8). Provider rows are edited here (enable, disable, weight, limits);
Django's own history records who changed what. Plans show counts, provider status and the selection log, never task titles: a
student's own task text is personal data and stays out of the admin.
"""

from django.contrib import admin

from . import registry
from .models import DayPlan, ProviderConfig


@admin.register(ProviderConfig)
class ProviderConfigAdmin(admin.ModelAdmin):
    list_display = ("provider", "registered", "enabled", "weight_pct", "max_candidates", "timeout_ms", "updated_at")
    list_filter = ("enabled",)
    search_fields = ("provider", "note")
    readonly_fields = ("updated_at", "updated_by")

    @admin.display(boolean=True, description="Registered")
    def registered(self, obj):
        return registry.get_provider(obj.provider) is not None


@admin.register(DayPlan)
class DayPlanAdmin(admin.ModelAdmin):
    list_display = (
        "local_date",
        "student",
        "phase",
        "status",
        "generation_no",
        "planned_count",
        "done_count",
        "open_count",
        "partial",
    )
    list_filter = ("status", "phase", "partial", "budget_source")
    date_hierarchy = "local_date"
    search_fields = ("user_id",)

    @admin.display(description="Student")
    def student(self, obj):
        return str(obj.user_id)

    def get_readonly_fields(self, request, obj=None):
        return [f.name for f in DayPlan._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
