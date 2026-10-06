from __future__ import annotations

from rest_framework.exceptions import NotFound

from ..domain.enums import DeviceKind
from ..models import Device

#: The only columns a student ever sees. The encrypted endpoint and keys are not in this list on purpose.
PUBLIC_FIELDS = ("id", "label", "platform", "browser", "display_mode", "last_seen_at", "created_at")


def list_devices(user_id) -> list[dict]:
    """The student's active devices, most recently seen first. Never carries the endpoint, keys or hash."""
    return list(
        Device.objects.filter(user_id=user_id, revoked_at__isnull=True).order_by("-last_seen_at").values(*PUBLIC_FIELDS)
    )


def active_push_devices(user_id, *, only_device_id=None) -> list[Device]:
    """Active Web Push devices with their secrets (decrypted on load). For the send path only."""
    rows = Device.objects.filter(user_id=user_id, kind=DeviceKind.WEB_PUSH, revoked_at__isnull=True)
    if only_device_id is not None:
        rows = rows.filter(id=only_device_id)
    return list(rows.order_by("created_at"))


def get_active_device(user_id, device_id) -> Device:
    """The student's own active device, or a 404 (another student's and a removed device look the same)."""
    device = Device.objects.filter(id=device_id, user_id=user_id, revoked_at__isnull=True).first()
    if device is None:
        raise NotFound("Device not found.")
    return device
