"""
The one pipeline every notification passes through: gather the facts, ask `domain.policy` what to do, send, record.
No business rule lives here; `policy.decide` owns the rules and `device_health` owns when to give up on a device.

Records (one `Delivery` row per notification, channel and device, so a retry updates the same row):
  * a send writes one row per active device (`sent` or `failed`);
  * a suppression writes one device-less row carrying the reason;
  * a deferral (quiet hours) writes one device-less `queued` row. The job that delivers it at the end of the window is
    W3.2; until then a deferred notification stays visible in the inbox and is not pushed.
Rows from an earlier decision (device-less `queued` or `suppressed`) are replaced when the notification is sent.

`now` is when dispatch started and stamps every row, so a run is deterministic; the push call adds at most a few
seconds on top (the adapter's 5 s timeout), which is inside the 5 s lateness target's budget but not measured.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime

from . import channels, flags, selectors
from .channels import DeviceSecrets, PushMessage, SendResult, SendStatus, Urgency
from .domain import catalogue
from .domain.enums import Channel, DeliveryStatus, SuppressReason
from .domain.payload import build_payload, delivery_window, encode_payload
from .domain.policy import Action, PolicyInput, QuietPreference, decide
from .domain.quiet_hours import local_day_bounds
from .models import Delivery, Device, Notification
from .services import devices as device_service

logger = logging.getLogger(__name__)

DEVICE_KIND_LOG = "web_push"


@dataclass(frozen=True)
class DispatchResult:
    action: Action
    reason: SuppressReason | None = None
    deliver_at: datetime | None = None
    sent: int = 0
    failed: int = 0
    revoked: int = 0
    already_sent: int = 0

    @property
    def outcome(self) -> str:
        """`sent`, `failed`, `suppressed`, `deferred` or `already_sent`: the short answer a caller or a screen needs."""
        if self.action is Action.SUPPRESS:
            return "suppressed"
        if self.action is Action.DEFER:
            return "deferred"
        if self.sent:
            return "sent"
        if self.failed:
            return "failed"
        return "already_sent"


def _log(level: int, name: str, **fields: object) -> None:
    """One structured line, `name key=value ...`. Callers pass only the fields PRD section 10 lists: no secrets."""
    logger.log(
        level, "%s %s", name, " ".join(f"{k}={v}" for k, v in fields.items() if v is not None), extra={"push": fields}
    )


def dispatch(
    notification: Notification,
    *,
    now: datetime,
    intended_at: datetime | None = None,
    only_device_id=None,
) -> DispatchResult:
    """
    Decide and (when allowed) push `notification` to the student's active devices. Safe to call again for the same
    notification: devices that already got it are skipped, the rest are retried on their existing rows.
    `only_device_id` limits the send to one device (the test push).
    """
    spec = catalogue.get_event(notification.event)
    user_id = notification.user_id
    devices = selectors.active_push_devices(user_id, only_device_id=only_device_id)

    delivered = set(
        Delivery.objects.filter(
            notification=notification, channel=Channel.PUSH, status=DeliveryStatus.SENT
        ).values_list("device_id", flat=True)
    )
    if devices and all(device.id in delivered for device in devices):
        return DispatchResult(Action.SEND, already_sent=len(devices))

    decision = decide(_facts(notification, spec, devices, now, intended_at))

    if decision.action is Action.SUPPRESS:
        _record_unsent(notification, DeliveryStatus.SUPPRESSED, now, reason=decision.reason)
        _log(logging.INFO, "push_suppressed", event=spec.key, reason=decision.reason.value)
        return DispatchResult(Action.SUPPRESS, reason=decision.reason)
    if decision.action is Action.DEFER:
        _record_unsent(notification, DeliveryStatus.QUEUED, now)
        return DispatchResult(Action.DEFER, deliver_at=decision.deliver_at)
    return _send(notification, spec, devices, delivered, now, intended_at)


def _facts(notification, spec, devices, now, intended_at) -> PolicyInput:
    user_id = notification.user_id
    prefs = selectors.get_settings(user_id)
    start, end = local_day_bounds(now, prefs.timezone)
    return PolicyInput(
        spec=spec,
        now=now,
        master_on=prefs.push_master,
        channel_enabled=spec.system or catalogue.is_enabled(spec.category, Channel.PUSH, selectors.overrides(user_id)),
        has_active_device=bool(devices),
        quiet=QuietPreference(prefs.quiet_enabled, prefs.timezone, prefs.quiet_start, prefs.quiet_end),
        sent_today=selectors.sent_cap_count(user_id, start, end, exclude_notification_id=notification.id),
        event_disabled=flags.event_disabled(spec.key) or not flags.sending_enabled(user_id),
        intended_at=intended_at,
        expires_at=notification.expires_at,
    )


def _record_unsent(notification, status, now, *, reason: SuppressReason | None = None) -> None:
    Delivery.objects.update_or_create(
        notification=notification,
        channel=Channel.PUSH,
        device=None,
        defaults={
            "user_id": notification.user_id,
            "status": status,
            "suppress_reason": reason,
            "counts_toward_cap": False,
            "http_status": None,
            "error_code": None,
            "attempt": 1,
            "attempted_at": now,
            "sent_at": None,
        },
    )


def _send(notification, spec, devices, delivered, now, intended_at) -> DispatchResult:
    Delivery.objects.filter(
        notification=notification,
        channel=Channel.PUSH,
        device__isnull=True,
        status__in=[DeliveryStatus.QUEUED, DeliveryStatus.SUPPRESSED],
    ).delete()

    ttl, urgency = delivery_window(spec.priority, now, notification.expires_at)
    message = PushMessage(body=_encoded_payload(notification), ttl_seconds=ttl, urgency=Urgency(urgency))
    channel = channels.get_channel(channels.PUSH)
    lateness_ms = max(0, int((now - (intended_at or notification.created_at)).total_seconds() * 1000))

    sent = failed = revoked = already = 0
    for device in devices:
        if device.id in delivered:
            already += 1
            continue
        row = _claim_row(notification, device, now)
        result = _call(channel, device, message)
        if result.status is SendStatus.SENT:
            sent += 1
            _mark_sent(row, result, spec, device, now, lateness_ms)
        else:
            failed += 1
            revoked += _mark_failed(row, result, spec, device, now)
    return DispatchResult(Action.SEND, sent=sent, failed=failed, revoked=revoked, already_sent=already)


def _encoded_payload(notification) -> str:
    return encode_payload(
        build_payload(
            notification_id=notification.id,
            category=notification.category,
            title=notification.title,
            body=notification.body,
            tag=notification.tag,
            deep_link=notification.deep_link,
        )
    )


def _claim_row(notification, device: Device, now) -> Delivery:
    """The (notification, push, device) row, reset to `queued` for this attempt. A retry reuses the same row."""
    row, created = Delivery.objects.get_or_create(
        notification=notification,
        channel=Channel.PUSH,
        device=device,
        defaults={"user_id": notification.user_id, "status": DeliveryStatus.QUEUED, "attempted_at": now},
    )
    if not created:
        row.status = DeliveryStatus.QUEUED
        row.suppress_reason = None
        row.attempted_at = now
        row.save(update_fields=["status", "suppress_reason", "attempted_at", "updated_at"])
    return row


def _call(channel, device: Device, message: PushMessage) -> SendResult:
    secrets = DeviceSecrets(endpoint=device.endpoint_enc, p256dh=device.p256dh_enc, auth=device.auth_enc)
    try:
        return channel.send(secrets, message)
    except channels.ChannelNotConfigured:
        raise  # a deployment mistake: surface it, and do not count it against the device
    except Exception as exc:  # noqa: BLE001 - an adapter bug must not stop the other devices; keep only the class name
        _log(logging.ERROR, "push_adapter_error", error_type=type(exc).__name__)
        return SendResult.failed("unexpected")


def _mark_sent(row: Delivery, result: SendResult, spec, device: Device, now, lateness_ms: int) -> None:
    row.status = DeliveryStatus.SENT
    row.http_status = result.http_status
    row.error_code = None
    row.attempt = min(max(result.attempts, 1), 3)
    row.lateness_ms = lateness_ms
    row.sent_at = now
    row.counts_toward_cap = not spec.exempt  # priority 1 to 3; timer alerts never use up the student's budget
    row.save()
    device_service.record_success(device.id, now=now)
    _log(
        logging.INFO,
        "push_sent",
        event=spec.key,
        category=spec.category.value,
        device_kind=DEVICE_KIND_LOG,
        status=DeliveryStatus.SENT.value,
        http_status=result.http_status,
        lateness_ms=lateness_ms,
        attempt=row.attempt,
        sw_version=device.sw_version,
    )


def _mark_failed(row: Delivery, result: SendResult, spec, device: Device, now) -> int:
    """Records a failure and applies the health rule. Returns 1 when the device was revoked."""
    http_status = result.http_status or (410 if result.status is SendStatus.GONE else None)
    row.status = DeliveryStatus.FAILED
    row.http_status = http_status
    row.error_code = result.error_code or "failed"
    row.attempt = min(max(result.attempts, 1), 3)
    row.counts_toward_cap = False
    row.save()
    _log(logging.WARNING, "push_failed", event=spec.key, http_status=http_status, reason=row.error_code)
    revoke = device_service.record_failure(device.id, now=now, http_status=http_status)
    if revoke is None:
        return 0
    _log(logging.INFO, "push_device_revoked", event=spec.key, http_status=http_status, reason=revoke.value)
    return 1
