"""
Devices: registering a browser subscription, removing it, and keeping its health. All writes, each in a transaction.

Ownership rule: an endpoint is one physical browser profile. If a second student signs in on a browser that another
student used, the same endpoint arrives under a new account. We move the device to the current student (so the
previous student's alerts stop appearing on a screen they no longer sit at), but only when the request proves it holds
the subscription by presenting the same `p256dh` and `auth` secrets. Someone who merely learned an endpoint URL cannot
take a device over or redirect another student's alerts.
"""

from __future__ import annotations

import hmac
from dataclasses import dataclass
from datetime import datetime

from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.exceptions import NotFound

from core.fields import hmac_hex

from ..domain import device_health
from ..domain.devices import InvalidKeys, derive_label, validate_keys
from ..domain.enums import DeviceBrowser, DeviceKind, DevicePlatform, DisplayMode, RevokeReason
from ..domain.push_hosts import EndpointRejected, validate_endpoint
from ..errors import DeviceLimit, InvalidEndpoint
from ..models import Device

MAX_ACTIVE_DEVICES = 10


@dataclass(frozen=True)
class Registration:
    device: Device
    created: bool


def _active(user_id):
    return Device.objects.filter(user_id=user_id, revoked_at__isnull=True)


def _check_subscription(endpoint: str, p256dh: str, auth: str) -> None:
    try:
        validate_endpoint(endpoint)
        validate_keys(p256dh, auth)
    except (EndpointRejected, InvalidKeys) as exc:
        raise InvalidEndpoint(str(exc)) from None


def _same_secret(stored: str | None, given: str) -> bool:
    return stored is not None and hmac.compare_digest(stored.encode(), given.encode())


def register_device(
    user_id,
    *,
    endpoint: str,
    p256dh: str,
    auth: str,
    platform: str = DevicePlatform.OTHER,
    browser: str = DeviceBrowser.OTHER,
    display_mode: str = DisplayMode.BROWSER,
    sw_version: str | None = None,
    now: datetime | None = None,
) -> Registration:
    """
    Register or refresh a subscription. Idempotent on the endpoint hash: repeating the call updates the one row. A
    revoked row is reused (revocation cleared, health reset). Raises `InvalidEndpoint` and `DeviceLimit`.
    """
    _check_subscription(endpoint, p256dh, auth)
    now = now or timezone.now()
    endpoint_hash = hmac_hex(endpoint)
    fields = {
        "platform": platform,
        "browser": browser,
        "display_mode": display_mode,
        "label": derive_label(platform, browser, display_mode),
        "sw_version": sw_version or None,
    }
    for attempt in (1, 2):
        try:
            with transaction.atomic():
                return _upsert(user_id, endpoint, endpoint_hash, p256dh, auth, fields, now)
        except IntegrityError:  # two first registrations of one endpoint raced; the second sees the row on retry
            if attempt == 2:
                raise
    raise AssertionError("unreachable")  # pragma: no cover


def _upsert(user_id, endpoint, endpoint_hash, p256dh, auth, fields, now) -> Registration:
    row = Device.objects.select_for_update().filter(endpoint_hash=endpoint_hash).first()
    if row is None:
        _enforce_limit(user_id)
        device = Device.objects.create(
            user_id=user_id,
            kind=DeviceKind.WEB_PUSH,
            endpoint_enc=endpoint,
            endpoint_hash=endpoint_hash,
            p256dh_enc=p256dh,
            auth_enc=auth,
            last_seen_at=now,
            **fields,
        )
        return Registration(device, created=True)

    if row.user_id != user_id:
        if not (_same_secret(row.p256dh_enc, p256dh) and _same_secret(row.auth_enc, auth)):
            raise InvalidEndpoint("That push address is already in use.")
        _enforce_limit(user_id)
        row.user_id = user_id
    elif row.revoked_at is not None:
        _enforce_limit(user_id)

    row.p256dh_enc, row.auth_enc = p256dh, auth  # a re-subscription may bring new keys for the same endpoint
    for name, value in fields.items():
        setattr(row, name, value)
    row.last_seen_at = now
    row.revoked_at = None
    row.revoked_reason = None
    row.consecutive_failures = 0
    row.first_failure_at = None
    row.save()
    return Registration(row, created=False)


def _enforce_limit(user_id) -> None:
    if _active(user_id).count() >= MAX_ACTIVE_DEVICES:
        raise DeviceLimit(extra={"limit": MAX_ACTIVE_DEVICES})


def remove_device(user_id, device_id, *, now: datetime | None = None) -> None:
    """
    Soft-revoke the student's own device (reason `user_removed`); the next send skips it. Another student's or an
    unknown device is a 404. Removing an already removed device of one's own is a no-op, so DELETE is safe to repeat.
    """
    now = now or timezone.now()
    with transaction.atomic():
        row = Device.objects.select_for_update().filter(id=device_id, user_id=user_id).first()
        if row is None:
            raise NotFound("Device not found.")
        if row.revoked_at is None:
            row.revoked_at = now
            row.revoked_reason = RevokeReason.USER_REMOVED
            row.save(update_fields=["revoked_at", "revoked_reason", "updated_at"])


def touch_last_seen(user_id, device_id, *, now: datetime | None = None) -> bool:
    """Stamp `last_seen_at` on an active device of the student. False when there is no such device."""
    return (
        _active(user_id).filter(id=device_id).update(last_seen_at=now or timezone.now(), updated_at=timezone.now()) > 0
    )


def record_success(device_id, *, now: datetime) -> None:
    """The push service accepted a message: stamp it and clear the failure run."""
    health = device_health.on_success()
    Device.objects.filter(id=device_id).update(
        last_success_at=now,
        consecutive_failures=health.consecutive_failures,
        first_failure_at=health.first_failure_at,
        updated_at=timezone.now(),
    )


def record_failure(device_id, *, now: datetime, http_status: int | None) -> RevokeReason | None:
    """
    Count one failed notification (after the adapter's retries) and revoke when the health rule says so. Returns the
    revoke reason when the device was revoked by this call.
    """
    with transaction.atomic():
        row = Device.objects.select_for_update().filter(id=device_id).first()
        if row is None or row.revoked_at is not None:
            return None
        change = device_health.on_failure(
            device_health.Health(row.consecutive_failures, row.first_failure_at), now, http_status
        )
        row.consecutive_failures = change.health.consecutive_failures
        row.first_failure_at = change.health.first_failure_at
        row.last_failure_at = now
        if change.revoke is not None:
            row.revoked_at = now
            row.revoked_reason = change.revoke
        row.save()
    return change.revoke
