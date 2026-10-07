"""
Buttons on timer alerts (X-01.1 W3.6, FR-N12): minting the one-time tokens a push carries, and using one.

Using a token is one conditional UPDATE (`used_at IS NULL AND expires_at > now`), so two taps racing each other, or a
replay, act at most once. The tap then goes to `focus.services.act_from_notification` with the timer phase and version
the button was made for, so a timer that moved since changes nothing. The token itself is never stored or logged.
"""

from __future__ import annotations

import logging
import secrets
from dataclasses import dataclass, field
from datetime import datetime

from django.db import transaction
from django.utils import timezone

from modules.focus import services as focus_services
from modules.tracking.errors import TrackingError

from .. import flags
from ..domain import actions as buttons
from ..domain.enums import ButtonAction
from ..domain.payload import PayloadAction, link_with_notification
from ..errors import ActionUnavailable, NotificationsDisabled
from ..logs import log_event
from ..models import ActionToken, Notification
from . import inbox as inbox_service

STALE = "stale"


def buttons_enabled() -> bool:
    """Buttons are offered and taps accepted only while notifications are on and the button kill switch is not set."""
    return flags.master_enabled() and not flags.event_disabled(buttons.KILL_SWITCH)


def mint(
    notification: Notification,
    *,
    now: datetime,
    actions: tuple[ButtonAction, ...] | None = None,
    client_id=None,
    version: int | None = None,
) -> list[PayloadAction]:
    """
    Fresh one-time tokens for the buttons of `notification` (by default the ones its event and context call for),
    valid for `TOKEN_TTL`. Empty when the alert has no buttons or buttons are switched off.
    """
    if not buttons_enabled():
        return []
    context = notification.context or {}
    chosen = buttons.buttons_for(notification.event, context) if actions is None else actions
    client_id = client_id if client_id is not None else context.get("client_id")
    version = version if version is not None else context.get("version")
    if not chosen or client_id is None or version is None:
        return []
    rows, out = [], []
    for action in chosen:
        token = secrets.token_urlsafe(buttons.TOKEN_BYTES)
        rows.append(
            ActionToken(
                user_id=notification.user_id,
                notification=notification,
                timer_client_id=client_id,
                timer_version=int(version),
                action=action,
                token_hash=buttons.hash_token(token),
                expires_at=now + buttons.TOKEN_TTL,
            )
        )
        out.append(PayloadAction(action.value, buttons.button_title(action, context), token))
    ActionToken.objects.bulk_create(rows)
    return out


@dataclass(frozen=True)
class TapResult:
    """What the service worker shows after a tap: a notification replacing the alert (same tag)."""

    outcome: str
    title: str
    body: str
    tag: str
    url: str
    actions: list[PayloadAction] = field(default_factory=list)


def consume(token: str, *, now: datetime) -> ActionToken:
    """
    Spend a token: the single atomic UPDATE (ERD 2.8). Raises `ActionUnavailable` for a malformed, unknown, used or
    expired token alike.
    """
    if not buttons.well_formed(token):
        raise ActionUnavailable
    token_hash = buttons.hash_token(token)
    spent = ActionToken.objects.filter(token_hash=token_hash, used_at__isnull=True, expires_at__gt=now).update(
        used_at=now, updated_at=now
    )
    if spent != 1:
        raise ActionUnavailable
    return ActionToken.objects.select_related("notification").get(token_hash=token_hash)


def tap(token: str, *, now: datetime | None = None) -> TapResult:
    """A button was tapped. The token is the only credential: no sign-in is needed (the worker has none)."""
    now = now or timezone.now()
    if not buttons_enabled():
        raise NotificationsDisabled
    try:
        row = consume(token, now=now)
    except ActionUnavailable:
        log_event(logging.INFO, "push_action_rejected", reason="unavailable")
        raise
    if not flags.send_flag_enabled(row.user_id):
        raise NotificationsDisabled
    action = ButtonAction(row.action)
    try:
        with transaction.atomic():
            result = focus_services.act_from_notification(
                row.user_id,
                action=action.value,
                client_id=row.timer_client_id,
                version=row.timer_version,
                issued_at=row.expires_at - buttons.TOKEN_TTL,  # when the button was made, on the clock that made it
            )
    except TrackingError:  # the timer refused (a stopwatch is running, the round cannot change): nothing changed
        result = focus_services.ButtonResult(STALE)

    notification = row.notification
    inbox_service.mark_clicked(row.user_id, notification.id, now=now)  # the student engaged with this alert
    follow_up: list[PayloadAction] = []
    if action is ButtonAction.PAUSE and result.outcome in ("done", "already") and result.paused:
        follow_up = mint(
            notification, now=now, actions=(ButtonAction.RESUME,), client_id=result.client_id, version=result.version
        )
    copy = buttons.confirmation(action, result.outcome)
    log_event(logging.INFO, "push_action", event=notification.event, action=action.value, outcome=result.outcome)
    return TapResult(
        outcome=result.outcome,
        title=copy.title,
        body=copy.body,
        tag=notification.tag,
        url=link_with_notification(notification.deep_link, notification.id),
        actions=follow_up,
    )
