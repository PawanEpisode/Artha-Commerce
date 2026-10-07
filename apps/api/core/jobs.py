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
import os
import threading
import time
from collections.abc import Callable, Iterable
from datetime import datetime, timedelta
from typing import Any

from django.db import IntegrityError, connection, connections, transaction
from django.db.models import Q
from django.utils import timezone

from .models import Job

logger = logging.getLogger(__name__)

Handler = Callable[[dict], dict | None]

VISIBILITY_TIMEOUT = timedelta(minutes=5)
MAX_BACKOFF = timedelta(hours=1)
HEARTBEAT_INTERVAL = (
    60.0  # seconds; far under the 5 minute visibility timeout, so a healthy long job is never reclaimed
)
LIVENESS_FILE_DEFAULT = "/tmp/artha-worker.alive"  # noqa: S108 - a per-container liveness marker, not a secret
_handlers: dict[str, Handler] = {}
_local = threading.local()  # the job the current thread is running, so a handler can call `heartbeat()` between chunks


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


def parse_type_limits(spec: str | None, aliases: dict[str, tuple[str, ...]] | None = None) -> dict[str, int]:
    """
    "notes.ocr=1,notes.export_pdf=1" to {"notes.ocr": 1, "notes.export_pdf": 1}. `aliases` expands short names
    ({"ocr": ("notes.ocr",)}). A limit of 0 means "never claim this type on any worker"; bad pieces raise ValueError.
    """
    limits: dict[str, int] = {}
    for piece in (spec or "").split(","):
        piece = piece.strip()
        if not piece:
            continue
        name, sep, raw = piece.partition("=")
        name = name.strip()
        if not sep or not name or not raw.strip().isdigit():
            raise ValueError(f"Bad concurrency limit {piece!r}; expected type=number.")
        for full in (aliases or {}).get(name, (name,)):
            limits[full] = int(raw)
    return limits


def _blocked_types(limits: dict[str, int], types: Iterable[str] | None, stale: datetime) -> list[str]:
    """
    Types already at their cap across ALL workers. Runs inside the claim transaction after taking one Postgres advisory
    transaction lock per limited type (sorted, so two workers can never deadlock): the count and the claim that follows are
    then one atomic step and two workers can never both take the last slot. Running jobs whose lock went stale do not count,
    so a crashed job can be reclaimed even when the cap is 1.
    """
    wanted = [t for t in sorted(limits) if types is None or t in types]
    blocked: list[str] = []
    for job_type in wanted:
        if connection.vendor == "postgresql":
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", [f"core_job:{job_type}"])
        running = Job.objects.filter(type=job_type, status=Job.Status.RUNNING, locked_at__gte=stale).count()
        if running >= limits[job_type]:
            blocked.append(job_type)
    return blocked


def claim_next(
    *,
    types: Iterable[str] | None = None,
    worker: str = "worker",
    now: datetime | None = None,
    limits: dict[str, int] | None = None,
) -> Job | None:
    """
    Takes the next due job and marks it running, or None. Due means queued with `run_after` reached, or running but
    abandoned past the visibility timeout. A reclaimed job that is out of attempts is closed as failed, not retried.
    `limits` ({type: max running at once, over every worker}) skips types that are at their cap.
    """
    now = now or timezone.now()
    stale = now - VISIBILITY_TIMEOUT
    wanted = list(types) if types is not None else None
    while True:
        with transaction.atomic():
            candidates = Job.objects.filter(
                Q(status=Job.Status.QUEUED, run_after__lte=now) | Q(status=Job.Status.RUNNING, locked_at__lt=stale)
            )
            if wanted is not None:
                candidates = candidates.filter(type__in=wanted)
            if limits:
                blocked = _blocked_types(limits, wanted, stale)
                if blocked:
                    candidates = candidates.exclude(type__in=blocked)
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


def heartbeat(job: Job | None = None) -> bool:
    """
    Refreshes a running job's `locked_at` so it is not reclaimed while healthy. With no argument, uses the job the current
    thread is running (a long handler calls `jobs.heartbeat()` between chunks). Returns False when the lock is no longer
    ours (the job finished or was reclaimed), which a handler may treat as "stop".
    """
    job = job or getattr(_local, "job", None)
    if job is None:
        return False
    now = timezone.now()
    updated = Job.objects.filter(pk=job.pk, status=Job.Status.RUNNING, locked_by=job.locked_by).update(
        locked_at=now, updated_at=now
    )
    return bool(updated)


def current_job() -> Job | None:
    """The job the calling thread is running (None outside a handler): lets a handler see its own attempt count."""
    return getattr(_local, "job", None)


def requeue(job: Job) -> bool:
    """
    Hands a running job back untouched (graceful shutdown past the grace period): queued again at once and the attempt
    refunded, because the job did not fail, the worker was told to stop. A no-op unless the job is still ours and running.
    """
    now = timezone.now()
    updated = Job.objects.filter(pk=job.pk, status=Job.Status.RUNNING, locked_by=job.locked_by).update(
        status=Job.Status.QUEUED,
        attempts=max(job.attempts - 1, 0),
        run_after=now,
        locked_at=None,
        locked_by="",
        updated_at=now,
    )
    return bool(updated)


def _execute(job: Job) -> tuple[bool, dict | None, str, bool]:
    """Runs the handler. Returns (ok, result, error, retry). Never raises and never touches the job row."""
    fn = _handlers.get(job.type)
    if fn is None:
        return False, None, f"No handler for job type {job.type!r}.", False
    _local.job = job
    try:
        result = fn(job.payload)
    except Exception as exc:  # noqa: BLE001 - a bad job must never stop the worker or the cron tick
        logger.exception("Job %s (%s) failed", job.id, job.type)
        return False, None, f"{type(exc).__name__}: {exc}", True
    finally:
        _local.job = None
    return True, result if isinstance(result, dict) else None, "", True


def _record(job: Job, outcome: tuple[bool, dict | None, str, bool], started: float) -> str:
    ok, result, error, retry = outcome
    if ok:
        complete(job, result)
    else:
        fail(job, error, retry=retry)
    # One line per job, never the payload: type, outcome and how long it took.
    logger.info(
        "job type=%s status=%s attempts=%s duration_ms=%d",
        job.type,
        job.status,
        job.attempts,
        round((time.monotonic() - started) * 1000),
    )
    return job.status


def run_job(job: Job) -> str:
    """Runs one claimed job through its handler and records the outcome. Never raises. Returns the final status."""
    started = time.monotonic()
    return _record(job, _execute(job), started)


def run_supervised(
    job: Job,
    *,
    stop: threading.Event | None = None,
    heartbeat_interval: float = HEARTBEAT_INTERVAL,
    grace: float | None = None,
    poll: float = 0.25,
    on_tick: Callable[[], None] | None = None,
) -> str:
    """
    Runs the handler in a thread while this thread keeps the job's lock fresh (`heartbeat` every `heartbeat_interval`).
    Once `stop` is set the job gets `grace` more seconds (None: as long as it needs); past that it is requeued and
    abandoned and "queued" is returned. The outcome is only recorded here, from the calling thread, so an abandoned
    handler can never overwrite a job that another worker has since claimed.
    """
    started = time.monotonic()
    done = threading.Event()
    box: dict[str, Any] = {}

    def target() -> None:
        try:
            box["outcome"] = _execute(job)
        finally:
            connections.close_all()  # the thread's own database connection
            done.set()

    threading.Thread(target=target, name=f"job-{job.type}", daemon=True).start()
    last_beat = time.monotonic()
    stop_seen: float | None = None
    while not done.wait(poll):
        now = time.monotonic()
        if on_tick:
            on_tick()
        if now - last_beat >= heartbeat_interval:
            heartbeat(job)
            last_beat = now
        if stop is not None and stop.is_set():
            stop_seen = stop_seen if stop_seen is not None else now
            if grace is not None and now - stop_seen >= grace:
                requeue(job)
                logger.warning("job type=%s status=requeued reason=shutdown", job.type)
                job.refresh_from_db()
                return job.status
    return _record(job, box["outcome"], started)


def touch_liveness(path: str | None = None) -> None:
    """Marks "the worker loop is alive" for `worker_health` and the container HEALTHCHECK (a file's mtime)."""
    target = path or os.environ.get("WORKER_LIVENESS_FILE", LIVENESS_FILE_DEFAULT)
    try:
        with open(target, "a"):
            os.utime(target, None)
    except OSError:
        pass  # a read-only filesystem must not stop the worker


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
