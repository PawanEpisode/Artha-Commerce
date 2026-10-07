"""
The weekly summary for one student (X-01.1 W3.5, FR-N13). The sweep step finds who is due; this module does one
student: claim the due time, judge it, read the week, skip a week with nothing to say, create the notification once
(the inbox row, `weekly:{iso_week}`) and send the email.

At most once per week, and a failed send is retried a bounded number of times. The claim is a compare-and-set that
moves `next_weekly_at` to the next Sunday before anything is sent, so two sweeps can never both send it. When the mail
server fails, the due time is put back 15 minutes (up to `MAX_ATTEMPTS` tries in all) and the delivery row keeps the count.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from enum import StrEnum

from django.utils import timezone

from .. import flags
from ..channels import ChannelNotConfigured
from ..domain.enums import Channel, DeliveryStatus
from ..domain.weekly import WeeklyVerdict, iso_week_key, judge_weekly, next_weekly_at, weekly_local_date, worth_sending
from ..logs import log_event
from ..models import Delivery, NotificationSettings
from ..selectors import weekly as weekly_selectors
from . import email_delivery
from . import notify as notify_service

EVENT = email_delivery.EVENT
RETRY_AFTER = timedelta(minutes=15)


class WeeklyOutcome(StrEnum):
    SENT = "sent"
    SUPPRESSED = "suppressed"  # the policy said no (switched off, no address); see the delivery row
    FAILED = "failed"  # the mail server refused; retried later when attempts remain
    NOTHING_TO_SAY = "nothing_to_say"  # no study time and nothing due: the week is skipped
    ALREADY = "already"
    NOT_DUE = "not_due"
    STALE = "stale"
    FLAG_OFF = "flag_off"


def process_due_weekly(user_id, *, now: datetime) -> WeeklyOutcome:
    """Handle one student whose weekly summary is due. Raises only for unexpected errors, which the sweep isolates."""
    row = NotificationSettings.objects.filter(pk=user_id, next_weekly_at__isnull=False, next_weekly_at__lte=now).first()
    if row is None:
        return WeeklyOutcome.NOT_DUE
    due_at = row.next_weekly_at
    following = next_weekly_at(now, row.timezone)
    claimed = NotificationSettings.objects.filter(pk=user_id, next_weekly_at=due_at).update(
        next_weekly_at=following, updated_at=timezone.now()
    )
    if not claimed:
        return WeeklyOutcome.NOT_DUE

    if judge_weekly(now=now, due_at=due_at) is WeeklyVerdict.STALE:
        log_event(logging.INFO, "weekly_skipped", event=EVENT, reason="stale")
        return WeeklyOutcome.STALE
    if not flags.sending_enabled(user_id):
        log_event(logging.INFO, "weekly_skipped", event=EVENT, reason="flag_off")
        return WeeklyOutcome.FLAG_OFF

    local_day = weekly_local_date(due_at, row.timezone)
    facts = weekly_selectors.weekly_facts(user_id, local_day)
    if not worth_sending(facts):
        log_event(logging.INFO, "weekly_skipped", event=EVENT, reason="nothing_to_say")
        return WeeklyOutcome.NOTHING_TO_SAY

    notification, created = notify_service.create_notification(
        user_id,
        EVENT,
        context={
            "study_seconds": facts.study_seconds,
            "due_for_revision": facts.due_for_revision,
            "streak_days": facts.streak_days,
        },
        dedupe_parts={"iso_week": iso_week_key(local_day)},
        now=now,
    )
    if not created and _finished(notification):
        return WeeklyOutcome.ALREADY
    try:
        result = email_delivery.send_weekly(notification, facts, local_day, now=now)
    except ChannelNotConfigured:
        _put_back(user_id, following, now + RETRY_AFTER)  # a deployment mistake: try again once it is fixed
        raise
    if result.status is DeliveryStatus.SENT:
        return WeeklyOutcome.SENT
    if result.status is DeliveryStatus.SUPPRESSED:
        return WeeklyOutcome.SUPPRESSED
    if result.attempt < email_delivery.MAX_ATTEMPTS:
        _put_back(user_id, following, now + RETRY_AFTER)
    return WeeklyOutcome.FAILED


def _finished(notification) -> bool:
    """The email for this week is done (sent, or deliberately not sent), or ran out of attempts."""
    row = Delivery.objects.filter(notification=notification, channel=Channel.EMAIL, device__isnull=True).first()
    if row is None:
        return False
    if row.status in (DeliveryStatus.SENT, DeliveryStatus.SUPPRESSED):
        return True
    return row.attempt >= email_delivery.MAX_ATTEMPTS


def _put_back(user_id, claimed: datetime, retry_at: datetime) -> None:
    NotificationSettings.objects.filter(pk=user_id, next_weekly_at=claimed).update(
        next_weekly_at=retry_at, updated_at=timezone.now()
    )
