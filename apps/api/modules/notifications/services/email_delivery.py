"""
Sends the weekly email for one notification and records what happened (one `Delivery` row, channel `email`, no device,
so a retry updates the same row). The rules are `domain.email_policy`; the words are `domain.email_copy`. Email stays
out of the push pipeline (`dispatch`) on purpose: it has no devices, quiet hours or daily cap, and a failure here must
never touch a push device's health.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime

from django.conf import settings

from .. import channels, flags, selectors
from ..domain import email_copy, unsubscribe
from ..domain.catalogue import get_event
from ..domain.email_policy import EmailPolicyInput, decide_email
from ..domain.enums import Channel, DeliveryStatus, SuppressReason
from ..domain.weekly import WeeklyFacts, week_window
from ..logs import log_event
from ..models import Delivery, Notification
from ..selectors import weekly as weekly_selectors

MAX_ATTEMPTS = 3
EVENT = "weekly_summary"
UNSUBSCRIBE_PATH = "/api/v1/notifications/unsubscribe/"


@dataclass(frozen=True)
class EmailResult:
    status: DeliveryStatus
    reason: SuppressReason | None = None
    attempt: int = 1


def unsubscribe_token(user_id, category: str) -> str:
    return unsubscribe.make_token(settings.SECRET_KEY, user_id=str(user_id), category=category)


def _links(token: str) -> tuple[email_copy.EmailLinks, str]:
    web = getattr(settings, "NOTIFICATIONS_WEB_BASE_URL", "")
    api = getattr(settings, "NOTIFICATIONS_PUBLIC_BASE_URL", "")
    if not web or not api:
        raise channels.ChannelNotConfigured("NOTIFICATIONS_WEB_BASE_URL and NOTIFICATIONS_PUBLIC_BASE_URL are needed")
    links = email_copy.EmailLinks(
        app=f"{web}/app", settings=f"{web}/app/settings/notifications", unsubscribe=f"{web}/unsubscribe?t={token}"
    )
    return links, f"{api}{UNSUBSCRIBE_PATH}?t={token}"


def send_weekly(notification: Notification, facts: WeeklyFacts, local_day: date, *, now: datetime) -> EmailResult:
    """Decide, send and record. Safe to call again: a row that is already `sent` or `suppressed` is left alone."""
    user_id = notification.user_id
    row = Delivery.objects.filter(notification=notification, channel=Channel.EMAIL, device__isnull=True).first()
    if row is not None and row.status in (DeliveryStatus.SENT, DeliveryStatus.SUPPRESSED):
        return EmailResult(
            DeliveryStatus(row.status),
            SuppressReason(row.suppress_reason) if row.suppress_reason else None,
            row.attempt,
        )
    attempt = (row.attempt + 1) if row is not None else 1

    address = weekly_selectors.email_address(user_id)
    decision = decide_email(
        EmailPolicyInput(
            now=now,
            master_on=selectors.get_settings(user_id).push_master,
            channel_enabled=weekly_selectors.email_enabled(user_id),
            has_address=bool(address),
            event_disabled=flags.event_disabled(EVENT) or not flags.sending_enabled(user_id),
            expires_at=notification.expires_at,
        )
    )
    if not decision.send:
        _record(notification, DeliveryStatus.SUPPRESSED, now, reason=decision.reason)
        log_event(logging.INFO, "email_suppressed", event=EVENT, reason=decision.reason.value)
        return EmailResult(DeliveryStatus.SUPPRESSED, decision.reason)

    token = unsubscribe_token(user_id, get_event(EVENT).category.value)
    links, one_click = _links(token)
    first, last = week_window(local_day)
    content = email_copy.build_weekly_email(facts, first=first, last=last, links=links)
    message = channels.EmailMessage(
        to=address,
        subject=content.subject,
        text=content.text,
        html=content.html,
        headers={"List-Unsubscribe": f"<{one_click}>", "List-Unsubscribe-Post": "List-Unsubscribe=One-Click"},
    )
    result = channels.get_channel(channels.EMAIL).send(message)
    if result.status is channels.SendStatus.SENT:
        _record(notification, DeliveryStatus.SENT, now, attempt=attempt, http_status=result.http_status)
        log_event(logging.INFO, "email_sent", event=EVENT, category=get_event(EVENT).category.value, attempt=attempt)
        return EmailResult(DeliveryStatus.SENT, attempt=attempt)
    _record(notification, DeliveryStatus.FAILED, now, attempt=attempt, error_code=result.error_code or "failed")
    log_event(logging.WARNING, "email_failed", event=EVENT, reason=result.error_code, attempt=attempt)
    return EmailResult(DeliveryStatus.FAILED, attempt=attempt)


def _record(notification, status, now, *, reason=None, attempt=1, http_status=None, error_code=None) -> None:
    Delivery.objects.update_or_create(
        notification=notification,
        channel=Channel.EMAIL,
        device=None,
        defaults={
            "user_id": notification.user_id,
            "status": status,
            "suppress_reason": reason,
            "counts_toward_cap": False,
            "http_status": http_status,
            "error_code": error_code,
            "attempt": min(attempt, MAX_ATTEMPTS),
            "attempted_at": now,
            "sent_at": now if status == DeliveryStatus.SENT else None,
        },
    )
