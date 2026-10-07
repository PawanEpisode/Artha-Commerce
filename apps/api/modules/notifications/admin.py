from django import forms
from django.contrib import admin, messages
from django.utils.html import format_html

from core.admin_base import ReadOnlyAdmin

from .domain.enums import MessageStatus
from .models import Delivery, Device, Message, MessageShown, Notification, NotificationSettings, ScheduledJob
from .services import motivation as motivation_service


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


class MessageForm(forms.ModelForm):
    class Meta:
        model = Message
        fields = ("body", "attribution", "tone", "phase", "course", "level", "locale")

    def clean(self):
        cleaned = super().clean()
        course, level = cleaned.get("course"), cleaned.get("level")
        if course and level and level.course_id != course.pk:
            raise forms.ValidationError("The level does not belong to the course.")
        return cleaned


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    """
    The motivation library. Editors write lines (they start as drafts), read them, and publish; only published lines are
    ever shown on the thought card or sent as the daily nudge, so nothing goes out from a draft. Status changes only
    through the two actions, which check the line first. A line a student may already have seen cannot be edited or
    deleted: retire it and write a new one, so what students were shown stays true.
    """

    form = MessageForm
    list_display = ("short_body", "tone", "phase", "course", "level", "status", "length_note", "published_at")
    list_filter = ("status", "tone", "phase", "course", "level")
    search_fields = ("body", "attribution")
    list_select_related = ("course", "level")
    readonly_fields = ("status", "published_at", "seed_key", "created_at", "updated_at")
    fields = (
        "body",
        "attribution",
        "tone",
        "phase",
        "course",
        "level",
        "locale",
        "status",
        "published_at",
        "seed_key",
        "created_at",
        "updated_at",
    )
    actions = ("publish_selected", "retire_selected")

    @admin.display(description="Text", ordering="body")
    def short_body(self, obj):
        return obj.body if len(obj.body) <= 70 else f"{obj.body[:69]}…"

    @admin.display(description="Length")
    def length_note(self, obj):
        # Lock screens show about 100 characters before they fold the text: longer lines still work, just less neatly.
        return (
            format_html("{}", len(obj.body))
            if len(obj.body) <= motivation_service.BODY_ADVISED
            else f"{len(obj.body)} (long)"
        )

    def get_readonly_fields(self, request, obj=None):
        locked = obj is not None and obj.status != MessageStatus.DRAFT
        return (
            (*self.readonly_fields, "body", "attribution", "tone", "phase", "course", "level", "locale")
            if locked
            else self.readonly_fields
        )

    def has_delete_permission(self, request, obj=None):
        return obj is None or obj.status == MessageStatus.DRAFT

    @admin.action(description="Publish selected (show to students)")
    def publish_selected(self, request, queryset):
        review = motivation_service.publish(queryset.select_related("level"))
        if review.changed:
            self.message_user(request, f"Published {review.changed} message(s).", messages.SUCCESS)
        for message_id, reasons in review.refused.items():
            self.message_user(request, f"Not published ({message_id}): {' '.join(reasons)}", messages.WARNING)

    @admin.action(description="Retire selected (stop using, keep history)")
    def retire_selected(self, request, queryset):
        self.message_user(request, f"Retired {motivation_service.retire(queryset)} message(s).", messages.SUCCESS)


@admin.register(MessageShown)
class MessageShownAdmin(ReadOnlyAdmin):
    """Support view: which line a student got on which day (never the push endpoint or any secret)."""

    list_display = ("user_id", "shown_on", "channel", "message")
    list_filter = ("channel",)
    search_fields = ("user_id",)
    list_select_related = ("message",)
