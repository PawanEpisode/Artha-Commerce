"""
The per-minute safety net (PRD 9.2, FR-N16/N17). Called by pg_cron (POST) or Vercel cron (GET) with the cron secret.

A run is a list of steps sharing one budget (jobs and seconds), so a Vercel function (30 s limit) never times out
mid-batch; whatever is left runs in the next minute. Today there is one step, firing overdue jobs. Nudges, digests and
pruning (waves W3.x, W2.7) are further steps appended to `STEPS`: each takes a `SweepRun` and reports what it did.

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

from ..domain.enums import JobStatus
from ..errors import TransientJobError
from ..logs import log_event
from ..models import ScheduledJob
from . import jobs

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


STEPS: tuple[Callable[[SweepRun], None], ...] = (fire_overdue_jobs,)


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
