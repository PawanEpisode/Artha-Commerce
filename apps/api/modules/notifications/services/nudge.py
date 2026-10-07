"""
The daily nudge for one student (X-01.1 W3.3, FR-N10). The sweep step finds who is due; this module does one student:
claim the due time, judge it, pick the day's message, create the notification once for the day and hand it to the
normal pipeline (`notify.deliver`), where preferences, quiet hours, the daily cap, the switches and "already opened the
app today" are decided in one place (`domain.policy`).

At most once per due time. The claim is a compare-and-set that moves `next_nudge_at` to the next occurrence before
anything is sent, so two sweeps, or a sweep and a retry, can never both send the same nudge; if a send fails after the
claim, the day's nudge is lost, which for a motivational line is cheaper than sending it twice. The notification's dedupe
key (`nudge:{local_date}`) is the second guard: even a hand-reset `next_nudge_at` cannot make a second push for one day.
"""

from __future__ import annotations

import logging
from datetime import datetime
from enum import StrEnum

from django.utils import timezone

from .. import flags
from ..domain.enums import ShownChannel
from ..domain.nudge import NudgeVerdict, judge_nudge, next_nudge_at, nudge_local_date
from ..logs import log_event
from ..models import Delivery, NotificationSettings
from . import notify as notify_service
from . import thought as thought_service

EVENT = "daily_nudge"


class NudgeOutcome(StrEnum):
    NOTIFIED = "notified"  # created and handed to dispatch (which may still suppress or hold it: see the delivery row)
    ALREADY = "already"  # today's nudge exists and was already dispatched
    NOT_DUE = "not_due"  # changed or claimed by someone else between the read and the claim, or switched off
    STALE = "stale"  # overdue by more than it stays useful: skipped, the next one is planned
    FLAG_OFF = "flag_off"  # sending is off for this student
    NO_MESSAGE = "no_message"  # nothing in the library may be shown to them today


def process_due_nudge(user_id, *, now: datetime) -> NudgeOutcome:
    """Handle one student whose nudge is due. Raises only for unexpected errors, which the sweep isolates per student."""
    row = NotificationSettings.objects.filter(
        pk=user_id, nudge_enabled=True, push_master=True, next_nudge_at__isnull=False, next_nudge_at__lte=now
    ).first()
    if row is None:
        return NudgeOutcome.NOT_DUE
    due_at = row.next_nudge_at
    claimed = NotificationSettings.objects.filter(pk=user_id, next_nudge_at=due_at).update(
        next_nudge_at=next_nudge_at(now, row.timezone, row.nudge_time), updated_at=timezone.now()
    )
    if not claimed:
        return NudgeOutcome.NOT_DUE

    if judge_nudge(now=now, due_at=due_at) is NudgeVerdict.STALE:
        log_event(logging.INFO, "nudge_skipped", event=EVENT, reason="stale")
        return NudgeOutcome.STALE
    if not flags.send_flag_enabled(user_id):
        log_event(logging.INFO, "nudge_skipped", event=EVENT, reason="flag_off")
        return NudgeOutcome.FLAG_OFF

    local_date = nudge_local_date(due_at, row.timezone)
    reservation = thought_service.reserve_message(
        user_id, local_date=local_date, tone=row.nudge_tone, channel=ShownChannel.PUSH, now=now
    )
    if reservation is None:
        log_event(logging.INFO, "nudge_skipped", event=EVENT, reason="no_message")
        return NudgeOutcome.NO_MESSAGE
    message = reservation.message

    notification, created = notify_service.create_notification(
        user_id,
        EVENT,
        context={
            "message": message.body,
            "attribution": message.attribution,
            "local_date": local_date.isoformat(),
            "tone": row.nudge_tone,
        },
        dedupe_parts={"local_date": local_date},
        now=now,
    )
    if not created and Delivery.objects.filter(notification=notification).exists():
        return NudgeOutcome.ALREADY
    notify_service.deliver(notification, now=now, intended_at=due_at)
    return NudgeOutcome.NOTIFIED
