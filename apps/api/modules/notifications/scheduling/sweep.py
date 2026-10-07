"""
The per-minute safety net (PRD 9.2, FR-N16/N17). Called by pg_cron (POST) or Vercel cron (GET) with the cron secret.

A run is a list of steps sharing one budget (jobs and seconds), so a Vercel function (30 s limit) never times out
mid-batch; whatever is left runs in the next minute. Steps: firing overdue jobs, the streak-at-risk alert (W3.2), the daily nudge (W3.3), the delivery check (`push_slo_breach`) and the nightly
retention prune. Digests and the other calendar alerts (waves W3.x) are further steps appended to `STEPS`: each takes a `SweepRun` and reports what it did.

Safe to run concurrently with itself and with the queue: each job is claimed atomically by `fire_job`, so two workers
that pick the same job produce one delivery, and the loser simply moves on.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from django.utils import timezone

from ..domain import slo
from ..domain.enums import JobStatus
from ..errors import TransientJobError
from ..logs import log_event
from ..models import ScheduledJob
from ..selectors import push_slo_counts
from ..services import retention as retention_service
from . import jobs
from .nudges import send_daily_nudges
from .streak_alerts import send_streak_alerts
from .weekly import send_weekly_emails

MAX_JOBS = 200
MAX_SECONDS = 20.0
OVERDUE_GRACE = timedelta(seconds=10)  # the queue gets this long to deliver a job itself before the sweep steps in
BATCH = 50


@dataclass
class SweepRun:
    """What a step may spend, and what the run has done so far."""

    now: datetime  # the wall-clock time the run began
    max_jobs: int
    started: float
    deadline: float
    clock: Callable[[], float]
    fired: int = 0
    skipped: int = 0
    failed: int = 0
    more: bool = False  # work was left because a bound was hit
    seen: set = field(default_factory=set)

    @property
    def handled(self) -> int:
        return self.fired + self.skipped + self.failed

    def current_time(self) -> datetime:
        """The wall-clock time now: the start plus the run's own elapsed time, so lateness is measured honestly."""
        return self.now + timedelta(seconds=self.clock() - self.started)

    def out_of_budget(self) -> bool:
        return self.handled >= self.max_jobs or self.clock() >= self.deadline


def fire_overdue_jobs(run: SweepRun) -> None:
    """Fire pending jobs whose time has passed, oldest first, until the bound or the clock stops the step."""
    cutoff = run.now - OVERDUE_GRACE
    while True:
        if run.out_of_budget():
            run.more = True
            return
        ids = list(
            ScheduledJob.objects.filter(status=JobStatus.PENDING, fire_at__lte=cutoff)
            .exclude(pk__in=run.seen)
            .order_by("fire_at")
            .values_list("id", flat=True)[: min(BATCH, run.max_jobs - run.handled)]
        )
        if not ids:
            return
        for job_id in ids:
            if run.out_of_budget():
                run.more = True
                return
            run.seen.add(job_id)  # a job released for a retry is not picked again in this run
            _fire(run, job_id)


def _fire(run: SweepRun, job_id) -> None:
    try:
        result = jobs.fire_job(job_id, now=run.current_time())
    except TransientJobError:
        run.failed += 1
        return
    if result.outcome is jobs.FireOutcome.NOTIFIED:
        run.fired += 1
    elif result.outcome is jobs.FireOutcome.SKIPPED:
        run.skipped += 1
    # IGNORED: another worker claimed it between our read and our claim; nothing to count


def check_slo(run: SweepRun) -> None:
    """FR-N23: judge the last 15 minutes of pushes against the targets and log an error a Sentry rule watches."""
    start = run.now - timedelta(minutes=slo.WINDOW_MINUTES)
    sent, failed, lateness = push_slo_counts(start, run.now)
    verdict = slo.evaluate(accepted=sent, failed=failed, lateness_ms=lateness)
    if verdict.breached:
        log_event(
            logging.ERROR,
            "push_slo_breach",
            window_minutes=slo.WINDOW_MINUTES,
            attempts=verdict.attempts,
            accepted_ratio=verdict.accepted_ratio,
            p95_ms=verdict.p95_ms,
            ratio_breached=verdict.ratio_breached,
            lateness_breached=verdict.lateness_breached,
        )


PRUNE_AT_UTC = (21, 30)  # 03:00 in India, the quietest hour. The window is a few runs; extra runs are no-ops.
PRUNE_WINDOW = timedelta(minutes=5)
PRUNE_MAX_ROWS = 20_000  # per run, so one run stays inside the function limit; the next minute carries on


def prune_nightly(run: SweepRun) -> None:
    """FR-N24: once a night, inside a short window, delete expired rows in small batches."""
    start = run.now.replace(hour=PRUNE_AT_UTC[0], minute=PRUNE_AT_UTC[1], second=0, microsecond=0)
    if not start <= run.now < start + PRUNE_WINDOW:
        return
    retention_service.prune(now=run.now, max_rows=PRUNE_MAX_ROWS, out_of_time=lambda: run.clock() >= run.deadline)


def _guarded(step: Callable[[SweepRun], None]) -> Callable[[SweepRun], None]:
    """Housekeeping must never stop jobs from firing: a failing check is logged and the run goes on."""

    def run_step(run: SweepRun) -> None:
        try:
            step(run)
        except Exception as exc:  # noqa: BLE001 - keep only the class name; the sweep itself must complete
            log_event(logging.ERROR, "sweep_step_failed", step=step.__name__, error_type=type(exc).__name__)

    run_step.__name__ = step.__name__
    return run_step


STEPS: tuple[Callable[[SweepRun], None], ...] = (
    fire_overdue_jobs,
    _guarded(send_streak_alerts),
    _guarded(send_daily_nudges),
    _guarded(send_weekly_emails),
    _guarded(check_slo),
    _guarded(prune_nightly),
)


def run_sweep(
    *,
    now: datetime | None = None,
    max_jobs: int = MAX_JOBS,
    max_seconds: float = MAX_SECONDS,
    clock: Callable[[], float] = time.monotonic,
) -> SweepRun:
    started = clock()
    run = SweepRun(
        now=now or timezone.now(), max_jobs=max_jobs, started=started, deadline=started + max_seconds, clock=clock
    )
    for step in STEPS:
        step(run)
    log_event(
        logging.INFO,
        "sweep_run",
        fired=run.fired,
        skipped=run.skipped,
        failed=run.failed,
        more=run.more,
        duration_ms=int((clock() - started) * 1000),
    )
    return run
