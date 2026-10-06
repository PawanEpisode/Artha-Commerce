from django.contrib import admin

from core.admin_base import ReadOnlyAdmin

from .models import Delivery, Device, Notification, NotificationSettings, ScheduledJob


@admin.register(NotificationSettings)
class SettingsAdmin(ReadOnlyAdmin):
    list_display = ("user_id", "push_master", "permission_state", "timezone", "updated_at")
    list_filter = ("permission_state", "push_master")
    search_fields = ("user_id",)


@admin.register(Device)
class DeviceAdmin(ReadOnlyAdmin):
    """Support view. Encrypted endpoint and keys are never shown."""

    list_display = ("user_id", "kind", "platform", "browser", "last_success_at", "consecutive_failures", "revoked_at")
    list_filter = ("kind", "platform", "browser", "revoked_reason")
    search_fields = ("user_id",)
    exclude = ("endpoint_enc", "endpoint_hash", "p256dh_enc", "auth_enc")


@admin.register(Notification)
class NotificationAdmin(ReadOnlyAdmin):
    list_display = ("user_id", "event", "priority", "created_at", "read_at")
    list_filter = ("event", "category", "priority")
    search_fields = ("user_id", "dedupe_key")


@admin.register(Delivery)
class DeliveryAdmin(ReadOnlyAdmin):
    list_display = ("user_id", "channel", "status", "suppress_reason", "http_status", "attempted_at")
    list_filter = ("channel", "status", "suppress_reason")
    search_fields = ("user_id",)


@admin.register(ScheduledJob)
class ScheduledJobAdmin(ReadOnlyAdmin):
    list_display = ("user_id", "kind", "status", "skip_reason", "fire_at", "fired_at")
    list_filter = ("kind", "status", "skip_reason")
    search_fields = ("user_id", "subject_key")
