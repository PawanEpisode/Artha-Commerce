"""
The weekly email sweep step (X-01.1 W3.5). Same shape as the daily nudge step: each minute, find the students whose
`next_weekly_at` has passed, in bounded batches, oldest first, and hand each to `services.weekly.process_due_weekly`.
One student's failure is logged and skipped. When the environment switch or the kill switch is off the step does
nothing; a summary overdue by more than a day is skipped as stale when sending comes back.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from .. import flags
from ..logs import log_event
from ..models import NotificationSettings
from ..services import settings as settings_service
from ..services import weekly as weekly_service

if TYPE_CHECKING:
    from .sweep import SweepRun

EVENT = weekly_service.EVENT
BATCH = 100
BACKFILL_PER_RUN = 200


def send_weekly_emails(run: SweepRun) -> None:
    if not flags.master_enabled() or flags.event_disabled(EVENT):
        return
    settings_service.backfill_next_weekly(run.now, limit=BACKFILL_PER_RUN)
    seen: set = set()
    while True:
        if run.out_of_budget():
            run.more = True
            return
        ids = list(
            NotificationSettings.objects.filter(next_weekly_at__lte=run.now)
            .exclude(pk__in=seen)
            .order_by("next_weekly_at")
            .values_list("user_id", flat=True)[: min(BATCH, max(1, run.max_jobs - run.handled))]
        )
        if not ids:
            return
        for user_id in ids:
            if run.out_of_budget():
                run.more = True
                return
            seen.add(user_id)
            _one(run, user_id)


def _one(run: SweepRun, user_id) -> None:
    try:
        outcome = weekly_service.process_due_weekly(user_id, now=run.current_time())
    except Exception as exc:  # noqa: BLE001 - one student's failure must not stop the others; no student data logged
        run.failed += 1
        log_event(logging.ERROR, "weekly_failed", event=EVENT, error_type=type(exc).__name__)
        return
    if outcome is weekly_service.WeeklyOutcome.SENT:
        run.fired += 1
    elif outcome is weekly_service.WeeklyOutcome.FAILED:
        run.failed += 1
    elif outcome is not weekly_service.WeeklyOutcome.NOT_DUE:
        run.skipped += 1
