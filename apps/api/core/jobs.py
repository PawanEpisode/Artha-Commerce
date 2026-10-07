"""
A minimal durable job queue on one Postgres table (`core_job`), shared by every module (F-06 ERD 2.27, F-03 ERD 3.3).

    enqueue("notes.purge", {...}, dedupe_key="notes.purge")   # safe to call twice: one active job per key
    claim_next()  ->  complete(job, result)  |  fail(job, "why")
    register_handler("notes.purge", fn)                       # fn(payload: dict) -> dict | None, at app start

Why a table and not a broker: Vercel functions are short-lived and stateless, so the queue must outlive them, and the
database is already the one thing every instance shares. Claiming uses `FOR UPDATE SKIP LOCKED` so several workers never
take the same row. A worker that dies leaves its job `running`; after `VISIBILITY_TIMEOUT` another worker reclaims it
(counting as an attempt), so a crash delays work and never loses it. Handlers must therefore be idempotent. Failures retry
with exponential backoff and end as `failed` after `max_attempts`; the error text is stored, the payload never is.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable, Iterable
from datetime import datetime, timedelta
from typing import Any

from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone

from .models import Job

logger = logging.getLogger(__name__)

Handler = Callable[[dict], dict | None]

VISIBILITY_TIMEOUT = timedelta(minutes=5)
MAX_BACKOFF = timedelta(hours=1)
_handlers: dict[str, Handler] = {}


def register_handler(job_type: str, fn: Handler) -> None:
    """Idempotent, so an app's `ready()` may run twice. A different function for the same type is a programming error."""
    existing = _handlers.get(job_type)
    if existing is not None and existing is not fn:
        raise ValueError(f"A handler for job type {job_type!r} is already registered.")
    _handlers[job_type] = fn


def handler_types() -> list[str]:
    return sorted(_handlers)


def _active(dedupe_key: str) -> Job | None:
    return Job.objects.filter(dedupe_key=dedupe_key, status__in=Job.ACTIVE_STATUSES).first()


def enqueue(
    job_type: str,
    payload: dict | None = None,
    *,
    dedupe_key: str | None = None,
    run_after: datetime | None = None,
    priority: int = 0,
    max_attempts: int = 5,
    once: bool = False,
) -> Job:
    """
    Queues a job. With a `dedupe_key`, an already queued or running job with that key is returned instead of a twin.
    With `once=True` a job with that key in ANY state counts, so "once per day" keys (`...:2026-10-07`) never run twice.
    """
    if dedupe_key:
        existing = Job.objects.filter(dedupe_key=dedupe_key).first() if once else _active(dedupe_key)
        if existing:
            return existing
    try:
        with transaction.atomic():  # a savepoint: losing the race must not poison the caller's transaction
            return Job.objects.create(
                type=job_type,
                payload=payload or {},
                dedupe_key=dedupe_key,
                run_after=run_after or timezone.now(),
                priority=priority,
                max_attempts=max_attempts,
            )
    except IntegrityError:
        existing = _active(dedupe_key) if dedupe_key else None
        if existing is None:
            raise
        return existing


def claim_next(
    *, types: Iterable[str] | None = None, worker: str = "worker", now: datetime | None = None
) -> Job | None:
    """
    Takes the next due job and marks it running, or None. Due means queued with `run_after` reached, or running but
    abandoned past the visibility timeout. A reclaimed job that is out of attempts is closed as failed, not retried.
    """
    now = now or timezone.now()
    stale = now - VISIBILITY_TIMEOUT
    while True:
        with transaction.atomic():
            candidates = Job.objects.filter(
                Q(status=Job.Status.QUEUED, run_after__lte=now) | Q(status=Job.Status.RUNNING, locked_at__lt=stale)
            )
            if types is not None:
                candidates = candidates.filter(type__in=list(types))
            job = (
                candidates.select_for_update(skip_locked=True).order_by("-priority", "run_after", "created_at").first()
            )
            if job is None:
                return None
            if job.attempts >= job.max_attempts:
                _close_failed(job, "Gave up: no attempts left after a worker stopped responding.", now)
                continue
            job.status = Job.Status.RUNNING
            job.attempts += 1
            job.locked_at = now
            job.locked_by = worker[:64]
            job.save(update_fields=["status", "attempts", "locked_at", "locked_by", "updated_at"])
            return job


def _close_failed(job: Job, error: str, now: datetime) -> None:
    job.status = Job.Status.FAILED
    job.last_error = error[:500]
    job.finished_at = now
    job.locked_at = None
    job.save(update_fields=["status", "last_error", "finished_at", "locked_at", "updated_at"])


def complete(job: Job, result: dict | None = None) -> None:
    job.status = Job.Status.DONE
    job.result = result
    job.finished_at = timezone.now()
    job.locked_at = None
    job.last_error = ""
    job.save(update_fields=["status", "result", "finished_at", "locked_at", "last_error", "updated_at"])


def fail(job: Job, error: str, *, retry: bool = True) -> None:
    """Back to the queue with exponential backoff (30 s, 1 min, 2 min, ...) until the attempts run out, then `failed`."""
    now = timezone.now()
    if not retry or job.attempts >= job.max_attempts:
        _close_failed(job, error, now)
        return
    job.status = Job.Status.QUEUED
    job.run_after = now + min(timedelta(seconds=30 * 2 ** (job.attempts - 1)), MAX_BACKOFF)
    job.last_error = error[:500]
    job.locked_at = None
    job.save(update_fields=["status", "run_after", "last_error", "locked_at", "updated_at"])


def run_job(job: Job) -> str:
    """Runs one claimed job through its handler and records the outcome. Never raises. Returns the final status."""
    fn = _handlers.get(job.type)
    if fn is None:
        fail(job, f"No handler for job type {job.type!r}.", retry=False)
        return job.status
    try:
        result = fn(job.payload)
    except Exception as exc:  # noqa: BLE001 - a bad job must never stop the worker or the cron tick
        logger.exception("Job %s (%s) failed", job.id, job.type)
        fail(job, f"{type(exc).__name__}: {exc}")
    else:
        complete(job, result if isinstance(result, dict) else None)
    return job.status


def run_pending(
    *, types: Iterable[str] | None = None, budget_seconds: float = 20.0, max_jobs: int = 50, worker: str = "tick"
) -> int:
    """Claims and runs due jobs until none are left, the time budget is spent or `max_jobs` ran. Returns how many ran."""
    deadline = time.monotonic() + budget_seconds
    wanted: list[str] | None = list(types) if types is not None else None
    ran = 0
    while ran < max_jobs and time.monotonic() < deadline:
        job = claim_next(types=wanted, worker=worker)
        if job is None:
            break
        run_job(job)
        ran += 1
    return ran


def prune_finished(*, older_than: timedelta = timedelta(days=7), now: datetime | None = None) -> int:
    """Deletes finished (done or failed) jobs older than `older_than`; keeps the table small and the once-keys fresh."""
    cutoff = (now or timezone.now()) - older_than
    deleted, _ = Job.objects.filter(status__in=[Job.Status.DONE, Job.Status.FAILED], finished_at__lt=cutoff).delete()
    return deleted


def clear_handlers() -> None:
    """Test helper."""
    _handlers.clear()


def describe(job: Job) -> dict[str, Any]:
    """A payload-free summary for logs and admin screens."""
    return {
        "id": str(job.id),
        "type": job.type,
        "status": job.status,
        "attempts": job.attempts,
        "error": job.last_error,
    }
