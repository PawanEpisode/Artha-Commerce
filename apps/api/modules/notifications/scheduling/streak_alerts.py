"""
The streak-at-risk alert (X-01.1 W3.2). A calendar alert, so it comes from the sweep and not from a job (ERD E3): there is
no event to react to, only the evening to notice. Each minute the step asks `tracking` which students have a streak that
ends at yesterday and a goal that is not met today, keeps those whose alert window is open now (90 minutes before their
day ends, see `domain.tracker_alerts`), and notifies each of them once for the day.

Idempotent and safe on retry: the alert's dedupe key (`streak:{local_date}`) holds one row per student per day, students
who already have it with a delivery record are skipped in one query before anything else, and a student whose goal is met
in the meantime drops out of `tracking`'s answer. A step that stops at its budget carries on next minute.
"""

from __future__ import annotations

import logging
import math
from collections.abc import Iterator, Sequence
from itertools import islice
from typing import TYPE_CHECKING

from modules.tracking import selectors as tracking_selectors

from .. import flags
from ..domain import tracker_alerts
from ..domain.catalogue import get_event
from ..domain.dedupe import build_dedupe_key
from ..domain.policy import QuietPreference
from ..logs import log_event
from ..models import Delivery, Notification, NotificationSettings
from ..services import notify as notify_service

if TYPE_CHECKING:
    from .sweep import SweepRun

EVENT = "streak_at_risk"
BATCH = 500


def _batches(items: Sequence, size: int) -> Iterator[list]:
    iterator = iter(items)
    while batch := list(islice(iterator, size)):
        yield batch


def _quiet(row: NotificationSettings) -> QuietPreference:
    return QuietPreference(row.quiet_enabled, row.timezone, row.quiet_start, row.quiet_end)


def send_streak_alerts(run: SweepRun) -> None:
    if not flags.master_enabled() or flags.event_disabled(EVENT):
        return
    spec = get_event(EVENT)
    risks = tracking_selectors.streaks_at_risk(run.now, local_from=tracker_alerts.STREAK_EARLIEST_LOCAL)
    for batch in _batches(risks, BATCH):
        settings_of = {
            row.user_id: row for row in NotificationSettings.objects.filter(user_id__in=[r.user_id for r in batch])
        }
        now = run.current_time()
        due = []
        for risk in batch:
            quiet = _quiet(settings_of.get(risk.user_id) or NotificationSettings(user_id=risk.user_id))
            window = tracker_alerts.streak_window(risk.local_date, risk.tz, quiet)
            if window and window[0] <= now < window[1]:
                due.append((risk, window[0], build_dedupe_key(spec, local_date=risk.local_date)))
        if not due:
            continue
        handled = set(
            Notification.objects.filter(
                user_id__in=[risk.user_id for risk, _, _ in due],
                dedupe_key__in={key for _, _, key in due},
                deliveries__isnull=False,
            ).values_list("user_id", "dedupe_key")
        )
        for risk, opens_at, key in due:
            if (risk.user_id, key) in handled:
                continue
            if run.out_of_budget():
                run.more = True
                return
            try:
                if _alert(risk, opens_at, run.current_time()):
                    run.fired += 1
            except Exception as exc:  # noqa: BLE001 - one student's failure must not stop the others; retried next minute
                log_event(logging.ERROR, "streak_alert_failed", error_type=type(exc).__name__)


def _alert(risk: tracking_selectors.GoalAtRisk, opens_at, now) -> bool:
    """Create and send one student's alert. False when there was nothing to do (no sending, no streak, already sent)."""
    if not flags.send_flag_enabled(risk.user_id):
        return False
    days = tracking_selectors.streak(risk.user_id, risk.local_date)
    if days < 1:
        return False
    notification, created = notify_service.create_notification(
        risk.user_id,
        EVENT,
        context={
            "local_date": risk.local_date.isoformat(),
            "streak_days": days,
            "remaining_minutes": max(1, math.ceil(risk.remaining_seconds / 60)),
        },
        dedupe_parts={"local_date": risk.local_date},
        now=now,
    )
    if not created and Delivery.objects.filter(notification=notification).exists():
        return False  # another run got there first
    notify_service.deliver(notification, now=now, intended_at=opens_at)
    return True
