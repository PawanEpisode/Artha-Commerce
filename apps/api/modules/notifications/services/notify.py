"""
Creating notifications and sending them. `notify` is the public interface for modules that cannot emit an event
(PRD 9.3): it creates the notification once per dedupe key and hands it to `dispatch`, which applies preferences,
quiet hours, the daily cap and the kill switches in one place.
"""

from __future__ import annotations

import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from django.utils import timezone

from .. import dispatch as dispatch_module
from .. import flags, selectors
from ..domain.catalogue import get_event
from ..domain.copy import build_copy
from ..domain.dedupe import build_dedupe_key, normalize_parts
from ..domain.deeplinks import InvalidDeepLink as DeepLinkRejected
from ..domain.deeplinks import validate_deep_link
from ..errors import InvalidDeepLink, NotificationsDisabled
from ..models import Notification


@dataclass(frozen=True)
class NotifyResult:
    notification: Notification
    created: bool  # False when the dedupe key already existed (a replayed event)
    dispatch: dispatch_module.DispatchResult


def create_notification(
    user_id,
    event_key: str,
    *,
    context: Mapping[str, Any],
    dedupe_parts: Mapping[str, object],
    now: datetime | None = None,
) -> tuple[Notification, bool]:
    """
    One notification per (student, dedupe key): replaying an event returns the existing row and creates nothing.
    Copy comes from `domain.copy`, the link is checked against the allow-list, `expires_at` comes from the catalogue.
    Raises `UnknownEvent` (an event not in the catalogue or without copy) and `InvalidDeepLink`.
    """
    now = now or timezone.now()
    spec = get_event(event_key)
    dedupe_key = build_dedupe_key(spec, **dedupe_parts)
    copy = build_copy(spec.key, context)
    try:
        deep_link = validate_deep_link(copy.deep_link)
    except DeepLinkRejected as exc:
        raise InvalidDeepLink(str(exc)) from None
    return Notification.objects.get_or_create(
        user_id=user_id,
        dedupe_key=dedupe_key,
        defaults={
            "category": spec.category.value,
            "event": spec.key,
            "title": copy.title,
            "body": copy.body,
            "deep_link": deep_link,
            "tag": copy.tag,
            "priority": spec.priority,
            "context": dict(context),
            "expires_at": now + spec.expires_after if spec.expires_after else None,
        },
    )


def notify(
    user_id,
    event_key: str,
    *,
    context: Mapping[str, Any],
    dedupe_ref: object,
    now: datetime | None = None,
    intended_at: datetime | None = None,
) -> NotifyResult:
    """
    Tell a student something. `dedupe_ref` is the single value of the event's dedupe template (an attempt id) or a
    mapping when the template has several parts. Calling twice with the same reference sends once.
    """
    now = now or timezone.now()
    notification, created = create_notification(
        user_id,
        event_key,
        context=context,
        dedupe_parts=normalize_parts(get_event(event_key), dedupe_ref),
        now=now,
    )
    result = dispatch_module.dispatch(notification, now=now, intended_at=intended_at)
    return NotifyResult(notification, created, result)


def send_test_push(user_id, device_id, *, now: datetime | None = None) -> dispatch_module.DispatchResult:
    """
    A real push to one of the student's own devices, so they can see it work. Each call is a new notification (the
    dedupe key carries a nonce). It is exempt from quiet hours and the cap, but still obeys the sending switches.
    404 for a device that is not theirs, 403 `notifications_disabled` when sending is off.
    """
    now = now or timezone.now()
    device = selectors.get_active_device(user_id, device_id)
    if not flags.sending_enabled(user_id):
        raise NotificationsDisabled
    notification, _ = create_notification(
        user_id, "test_push", context={}, dedupe_parts={"nonce": uuid.uuid4().hex}, now=now
    )
    return dispatch_module.dispatch(notification, now=now, only_device_id=device.id)
