"""
The daily slot for one student (X-01.1 W3.3 FR-N10, W3.4). The sweep step finds who is due; this module does one
student: claim the due time, judge it, decide what the slot carries today (an exam milestone, revision that is due, or
the daily thought: `domain.daily_slot`), create the notification once and hand it to the normal pipeline
(`notify.deliver`), where preferences, quiet hours, the daily cap, the switches and "already opened the app today" are
decided in one place (`domain.policy`). One slot, one push: a student never gets a thought and a revision reminder at
the same time.

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
from ..domain import daily_slot
from ..domain.enums import ShownChannel
from ..domain.nudge import NudgeVerdict, judge_nudge, next_nudge_at, nudge_local_date
from ..logs import log_event
from ..models import Delivery, NotificationSettings
from ..selectors import daily as daily_selectors
from . import notify as notify_service
from . import thought as thought_service

EVENT = "daily_nudge"
EXAM_EVENT = "exam_milestone"
REVISION_EVENT = "revision_due"


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
    pick = _pick(user_id, local_date)
    log_event(logging.INFO, "nudge_slot", slot=pick.slot.value)

    if pick.slot is daily_slot.Slot.EXAM:
        return _send(
            user_id,
            EXAM_EVENT,
            context={"days_left": pick.days_left},
            dedupe_parts={"days_left": pick.days_left},
            now=now,
            due_at=due_at,
        )
    if pick.slot is daily_slot.Slot.REVISION:
        facts = daily_selectors.daily_facts(user_id, local_date)
        return _send(
            user_id,
            REVISION_EVENT,
            context={
                "local_date": local_date.isoformat(),
                "due_count": facts.due_count,
                "first_chapter": facts.first_chapter,
            },
            dedupe_parts={"local_date": local_date},
            now=now,
            due_at=due_at,
        )

    reservation = thought_service.reserve_message(
        user_id, local_date=local_date, tone=row.nudge_tone, channel=ShownChannel.PUSH, now=now
    )
    if reservation is None:
        log_event(logging.INFO, "nudge_skipped", event=EVENT, reason="no_message")
        return NudgeOutcome.NO_MESSAGE
    message = reservation.message
    return _send(
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
        due_at=due_at,
    )


def _pick(user_id, local_date) -> daily_slot.Pick:
    """What the slot carries today. A category the student turned off for push, or an event switched off, is skipped."""
    facts = daily_selectors.daily_facts(user_id, local_date)
    allowed = daily_selectors.push_allowed(user_id, (EXAM_EVENT, REVISION_EVENT))
    return daily_slot.choose(
        days_left=facts.days_left,
        due_count=facts.due_count,
        exam_on=allowed[EXAM_EVENT] and not flags.event_disabled(EXAM_EVENT),
        revision_on=allowed[REVISION_EVENT] and not flags.event_disabled(REVISION_EVENT),
    )


def _send(user_id, event: str, *, context: dict, dedupe_parts: dict, now: datetime, due_at: datetime) -> NudgeOutcome:
    notification, created = notify_service.create_notification(
        user_id, event, context=context, dedupe_parts=dedupe_parts, now=now
    )
    if not created and Delivery.objects.filter(notification=notification).exists():
        return NudgeOutcome.ALREADY
    notify_service.deliver(notification, now=now, intended_at=due_at)
    return NudgeOutcome.NOTIFIED
