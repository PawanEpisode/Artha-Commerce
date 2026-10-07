"""
The daily nudge sweep step (X-01.1 W3.3). A calendar alert, so it comes from the sweep and not from a job (ERD E3):
each minute it finds the students whose `next_nudge_at` has passed, in bounded batches, oldest first, and hands each to
`services.nudge.process_due_nudge`. One student's failure is logged and skipped; the rest of the batch carries on, and a
step that stops at its budget carries on next minute (the due rows are still due).

When the environment switch or the kill switch for the event is off, the step does nothing and leaves the rows due; when
sending comes back, anything overdue by more than the nudge stays useful is skipped as stale and replanned, so a switch
that was off for a day never produces a burst of old nudges.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from .. import flags
from ..logs import log_event
from ..models import NotificationSettings
from ..services import nudge as nudge_service
from ..services import settings as settings_service

if TYPE_CHECKING:
    from .sweep import SweepRun

EVENT = nudge_service.EVENT
BATCH = 100
BACKFILL_PER_RUN = 200  # rows without a first nudge time that one run heals; the rest follow next minute


def send_daily_nudges(run: SweepRun) -> None:
    if not flags.master_enabled() or flags.event_disabled(EVENT):
        return
    settings_service.backfill_next_nudges(run.now, limit=BACKFILL_PER_RUN)
    seen: set = set()  # a student whose nudge failed stays due; do not pick them again in this run
    while True:
        if run.out_of_budget():
            run.more = True
            return
        ids = list(
            NotificationSettings.objects.filter(nudge_enabled=True, push_master=True, next_nudge_at__lte=run.now)
            .exclude(pk__in=seen)
            .order_by("next_nudge_at")
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
        outcome = nudge_service.process_due_nudge(user_id, now=run.current_time())
    except Exception as exc:  # noqa: BLE001 - one student's failure must not stop the others; logged, no student data
        run.failed += 1
        log_event(logging.ERROR, "nudge_failed", event=EVENT, error_type=type(exc).__name__)
        return
    if outcome is nudge_service.NudgeOutcome.NOTIFIED:
        run.fired += 1
    elif outcome is not nudge_service.NudgeOutcome.NOT_DUE:
        run.skipped += 1
