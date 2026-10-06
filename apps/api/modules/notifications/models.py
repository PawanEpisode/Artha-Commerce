# ruff: noqa: DJ001  (NULL means "not set" on the optional enum and key columns, and a unique hash needs NULL, not "")
"""
Push, email and inbox notifications (X-01.1). Every row is scoped by `user_id` (the Supabase user UUID, by value).
Allowed values of the choice columns come from `domain.enums`, the single source for the API, the checks and the tests.
See docs/product/erd/X-01.1-push-notifications.md section 2.
"""

from datetime import time

from django.db import models
from django.db.models import Q
from django.utils import timezone

from core.fields import EncryptedTextField
from core.models import TimeStampedModel, UUIDModel

from .domain import enums
from .domain.enums import choices, values


def _in(column: str, enum_class) -> Q:
    return Q(**{f"{column}__in": values(enum_class)})


class NotificationSettings(TimeStampedModel):
    """One row per student. Created on the first write (reads fall back to the defaults below)."""

    user_id = models.UUIDField(primary_key=True)
    push_master = models.BooleanField(default=True)
    timezone = models.CharField(max_length=64, default="Asia/Kolkata")
    quiet_enabled = models.BooleanField(default=True)
    quiet_start = models.TimeField(default=time(22, 0))
    quiet_end = models.TimeField(default=time(7, 0))
    nudge_enabled = models.BooleanField(default=True)
    nudge_time = models.TimeField(default=time(10, 0))
    nudge_tone = models.CharField(max_length=12, choices=choices(enums.Tone), default=enums.Tone.CALM)
    next_nudge_at = models.DateTimeField(null=True, blank=True)
    permission_state = models.CharField(
        max_length=16, choices=choices(enums.PermissionState), default=enums.PermissionState.NOT_ASKED
    )
    permission_source = models.CharField(max_length=12, choices=choices(enums.PermissionSource), null=True, blank=True)
    permission_decided_at = models.DateTimeField(null=True, blank=True)
    permission_ask_count = models.SmallIntegerField(default=0)
    last_asked_at = models.DateTimeField(null=True, blank=True)
    digest_offered_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "notifications_settings"
        constraints = [
            models.CheckConstraint(
                condition=Q(permission_ask_count__gte=0, permission_ask_count__lte=3), name="notif_settings_asks"
            ),
            models.CheckConstraint(condition=~Q(quiet_start=models.F("quiet_end")), name="notif_settings_quiet"),
            models.CheckConstraint(condition=_in("nudge_tone", enums.Tone), name="notif_settings_tone"),
            models.CheckConstraint(
                condition=_in("permission_state", enums.PermissionState), name="notif_settings_permission"
            ),
        ]
        indexes = [
            models.Index(
                fields=["next_nudge_at"],
                name="notif_settings_nudge_idx",
                condition=Q(nudge_enabled=True, push_master=True, next_nudge_at__isnull=False),
            )
        ]


class Preference(UUIDModel):
    """A student's change to one category and channel switch. No row means the catalogue default applies."""

    user_id = models.UUIDField()
    category = models.CharField(max_length=16)  # validated against the catalogue in the service
    channel = models.CharField(max_length=8, choices=choices(enums.Channel))
    enabled = models.BooleanField()

    class Meta:
        db_table = "notifications_preference"
        constraints = [
            models.UniqueConstraint(fields=["user_id", "category", "channel"], name="notif_preference_unique"),
            models.CheckConstraint(condition=_in("channel", enums.Channel), name="notif_preference_channel"),
        ]


class Device(UUIDModel):
    """A place a student can be reached: a browser or installed app (Web Push) or the desktop companion."""

    user_id = models.UUIDField()
    kind = models.CharField(max_length=12, choices=choices(enums.DeviceKind))
    endpoint_enc = EncryptedTextField(null=True, blank=True)
    endpoint_hash = models.CharField(max_length=64, null=True, blank=True, unique=True)
    p256dh_enc = EncryptedTextField(null=True, blank=True)
    auth_enc = EncryptedTextField(null=True, blank=True)
    platform = models.CharField(
        max_length=10, choices=choices(enums.DevicePlatform), default=enums.DevicePlatform.OTHER
    )
    browser = models.CharField(max_length=12, choices=choices(enums.DeviceBrowser), default=enums.DeviceBrowser.OTHER)
    display_mode = models.CharField(
        max_length=10, choices=choices(enums.DisplayMode), default=enums.DisplayMode.BROWSER
    )
    label = models.CharField(max_length=80, blank=True)
    app_version = models.CharField(max_length=20, null=True, blank=True)
    sw_version = models.CharField(max_length=16, null=True, blank=True)
    last_seen_at = models.DateTimeField(default=timezone.now)
    last_success_at = models.DateTimeField(null=True, blank=True)
    last_failure_at = models.DateTimeField(null=True, blank=True)
    first_failure_at = models.DateTimeField(null=True, blank=True)
    consecutive_failures = models.SmallIntegerField(default=0)
    revoked_at = models.DateTimeField(null=True, blank=True)
    revoked_reason = models.CharField(max_length=14, choices=choices(enums.RevokeReason), null=True, blank=True)

    class Meta:
        db_table = "notifications_device"
        constraints = [
            models.CheckConstraint(condition=_in("kind", enums.DeviceKind), name="notif_device_kind"),
            models.CheckConstraint(
                condition=~Q(kind=enums.DeviceKind.WEB_PUSH)
                | Q(
                    endpoint_enc__isnull=False,
                    endpoint_hash__isnull=False,
                    p256dh_enc__isnull=False,
                    auth_enc__isnull=False,
                ),
                name="notif_device_web_push_keys",
            ),
            models.CheckConstraint(condition=Q(consecutive_failures__gte=0), name="notif_device_failures"),
        ]
        indexes = [
            models.Index(fields=["user_id"], name="notif_device_active_idx", condition=Q(revoked_at__isnull=True)),
            models.Index(fields=["revoked_at"], name="notif_device_revoked_idx", condition=Q(revoked_at__isnull=False)),
        ]


class Notification(UUIDModel):
    """What we decided to tell the student. It is also the in-app inbox."""

    user_id = models.UUIDField()
    category = models.CharField(max_length=16)
    event = models.CharField(max_length=24)
    dedupe_key = models.CharField(max_length=120)
    title = models.CharField(max_length=80)
    body = models.CharField(max_length=240)
    deep_link = models.CharField(max_length=200)
    tag = models.CharField(max_length=80, blank=True)
    priority = models.SmallIntegerField()
    context = models.JSONField(default=dict)
    read_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "notifications_notification"
        constraints = [
            models.UniqueConstraint(fields=["user_id", "dedupe_key"], name="notif_notification_dedupe"),
            models.CheckConstraint(condition=Q(priority__gte=0, priority__lte=3), name="notif_notification_priority"),
            models.CheckConstraint(
                condition=Q(deep_link__startswith="/") & ~Q(deep_link__startswith="//"), name="notif_notification_link"
            ),
        ]
        indexes = [
            models.Index(fields=["user_id", "-created_at"], name="notif_inbox_idx"),
            models.Index(fields=["user_id"], name="notif_unread_idx", condition=Q(read_at__isnull=True)),
            models.Index(fields=["created_at"], name="notif_created_idx"),
        ]


class Delivery(UUIDModel):
    """One attempt to reach a student on one channel and device, including the ones we chose not to send."""

    notification = models.ForeignKey(Notification, on_delete=models.CASCADE, related_name="deliveries")
    user_id = models.UUIDField()  # denormalised on purpose: the cap and fatigue queries must not join
    device = models.ForeignKey(Device, null=True, blank=True, on_delete=models.SET_NULL, related_name="deliveries")
    channel = models.CharField(max_length=8, choices=choices(enums.Channel))
    status = models.CharField(max_length=10, choices=choices(enums.DeliveryStatus))
    suppress_reason = models.CharField(max_length=16, choices=choices(enums.SuppressReason), null=True, blank=True)
    counts_toward_cap = models.BooleanField(default=False)
    http_status = models.SmallIntegerField(null=True, blank=True)
    error_code = models.CharField(max_length=40, null=True, blank=True)
    attempt = models.SmallIntegerField(default=1)
    lateness_ms = models.IntegerField(null=True, blank=True)
    attempted_at = models.DateTimeField(default=timezone.now)
    sent_at = models.DateTimeField(null=True, blank=True)
    clicked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "notifications_delivery"
        constraints = [
            models.UniqueConstraint(
                fields=["notification", "channel", "device"], name="notif_delivery_unique", nulls_distinct=False
            ),
            models.CheckConstraint(condition=_in("status", enums.DeliveryStatus), name="notif_delivery_status"),
            models.CheckConstraint(
                condition=~Q(status=enums.DeliveryStatus.SUPPRESSED) | Q(suppress_reason__isnull=False),
                name="notif_delivery_reason",
            ),
            models.CheckConstraint(condition=Q(attempt__gte=1, attempt__lte=3), name="notif_delivery_attempt"),
        ]
        indexes = [
            models.Index(
                fields=["user_id", "-attempted_at"],
                name="notif_delivery_sent_idx",
                condition=Q(status=enums.DeliveryStatus.SENT),
            ),
            models.Index(fields=["notification"], name="notif_delivery_notif_idx"),
            models.Index(fields=["attempted_at"], name="notif_delivery_attempted_idx"),
        ]


class ScheduledJob(UUIDModel):
    """An exact-time piece of work started by an event (a timer ending, a long stopwatch)."""

    user_id = models.UUIDField()
    kind = models.CharField(max_length=20, choices=choices(enums.JobKind))
    subject_key = models.CharField(max_length=64)
    expected_version = models.IntegerField(default=0)
    fire_at = models.DateTimeField()
    context = models.JSONField(default=dict)
    status = models.CharField(max_length=10, choices=choices(enums.JobStatus), default=enums.JobStatus.PENDING)
    skip_reason = models.CharField(max_length=16, choices=choices(enums.SkipReason), null=True, blank=True)
    external_id = models.CharField(max_length=64, null=True, blank=True)
    attempts = models.SmallIntegerField(default=0)
    fired_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "notifications_scheduledjob"
        constraints = [
            models.UniqueConstraint(
                fields=["user_id", "kind", "subject_key", "expected_version"], name="notif_job_unique"
            ),
            models.CheckConstraint(condition=_in("status", enums.JobStatus), name="notif_job_status"),
            models.CheckConstraint(condition=_in("kind", enums.JobKind), name="notif_job_kind"),
        ]
        indexes = [
            models.Index(fields=["fire_at"], name="notif_job_due_idx", condition=Q(status=enums.JobStatus.PENDING)),
            models.Index(
                fields=["updated_at"], name="notif_job_prune_idx", condition=~Q(status=enums.JobStatus.PENDING)
            ),
        ]
