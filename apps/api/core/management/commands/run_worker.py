"""
Runs queued `core_job` rows until stopped (the always-on worker) or until the queue is empty (`--once`, for cron and tests).

    python manage.py run_worker                                  # forever, polls every 2 seconds when idle
    python manage.py run_worker --once                           # drain what is due now, then exit
    python manage.py run_worker --types notes.ocr                # only some job types
    python manage.py run_worker --concurrency ocr=1,export=1     # at most 1 OCR and 1 of each export type at once, over ALL workers

Environment equivalents (the container sets these): `WORKER_TYPE_LIMITS="notes.ocr=1,notes.export_pdf=1"`,
`WORKER_SHUTDOWN_GRACE_SECONDS` (default 25), `WORKER_HEARTBEAT_SECONDS` (default 60), `WORKER_LIVENESS_FILE`.

Long-running mode runs each handler in a thread while the main thread refreshes the job's lock every minute (a healthy long
job is never reclaimed by another worker) and watches for SIGTERM/SIGINT: the current job is allowed to finish, up to the grace
period; past that it is handed back to the queue and the process exits 0, so a deploy never loses or double-runs work.
"""

import logging
import os
import signal
import socket
import threading

from django.core.management.base import BaseCommand, CommandError
from django.db import DatabaseError, connection

from core import jobs

logger = logging.getLogger(__name__)

# Short names for `--concurrency`; full job type names always work too.
CONCURRENCY_ALIASES = {
    "inspect": ("notes.inspect",),
    "extract": ("notes.extract_text",),
    "ocr": ("notes.ocr",),
    "export": ("notes.export_pdf", "notes.export_archive"),
}
MAX_DB_BACKOFF = 30.0


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, default))
    except ValueError:
        return default


class Command(BaseCommand):
    help = "Claim and run background jobs from core_job."

    def add_arguments(self, parser):
        parser.add_argument("--once", action="store_true", help="Exit when no job is due.")
        parser.add_argument("--types", nargs="*", default=None, help="Only claim these job types.")
        parser.add_argument("--sleep", type=float, default=2.0, help="Seconds to wait when idle (default 2).")
        parser.add_argument("--max-jobs", type=int, default=0, help="Stop after this many jobs (0 = no limit).")
        parser.add_argument(
            "--concurrency",
            default=None,
            help="Per-type caps over all workers, e.g. ocr=1,export=1 (default: env WORKER_TYPE_LIMITS).",
        )
        parser.add_argument(
            "--grace",
            type=float,
            default=None,
            help="Seconds a job may keep running after SIGTERM before it is requeued (env WORKER_SHUTDOWN_GRACE_SECONDS).",
        )
        parser.add_argument(
            "--heartbeat", type=float, default=None, help="Seconds between lock refreshes (default 60)."
        )

    def handle(self, *args, once, types, sleep, max_jobs, concurrency=None, grace=None, heartbeat=None, **options):
        try:
            limits = jobs.parse_type_limits(
                concurrency if concurrency is not None else os.environ.get("WORKER_TYPE_LIMITS", ""),
                CONCURRENCY_ALIASES,
            )
        except ValueError as exc:
            raise CommandError(str(exc)) from exc
        grace = grace if grace is not None else _env_float("WORKER_SHUTDOWN_GRACE_SECONDS", 25.0)
        beat = heartbeat if heartbeat is not None else _env_float("WORKER_HEARTBEAT_SECONDS", jobs.HEARTBEAT_INTERVAL)

        stop = threading.Event()
        previous = self._install_signal_handlers(stop)
        worker = f"{socket.gethostname()}:{os.getpid()}"
        ran = 0
        failures = 0
        try:
            while not stop.is_set():
                jobs.touch_liveness()
                try:
                    self._ensure_connection()
                    job = jobs.claim_next(types=types, worker=worker, limits=limits or None)
                except DatabaseError as exc:
                    failures += 1
                    pause = min(MAX_DB_BACKOFF, sleep * 2**failures)
                    logger.warning(
                        "worker cannot reach the database (%s); retrying in %.0fs", type(exc).__name__, pause
                    )
                    connection.close()
                    if once:
                        raise
                    stop.wait(pause)
                    continue
                failures = 0
                if job is None:
                    if once:
                        break
                    stop.wait(sleep)
                    continue
                if once:
                    status = jobs.run_job(job)
                else:
                    status = jobs.run_supervised(
                        job, stop=stop, heartbeat_interval=beat, grace=grace, on_tick=jobs.touch_liveness
                    )
                ran += 1
                self.stdout.write(f"{job.type} {status}")
                if max_jobs and ran >= max_jobs:
                    break
        finally:
            self._restore_signal_handlers(previous)
        if stop.is_set():
            self.stdout.write("Stopping on request.")
        self.stdout.write(self.style.SUCCESS(f"Ran {ran} job(s)."))

    @staticmethod
    def _ensure_connection() -> None:
        """A long-lived loop outlives pooler idle timeouts: reconnect only when the connection is really dead."""
        connection.ensure_connection()
        if not connection.is_usable():
            connection.close()

    @staticmethod
    def _install_signal_handlers(stop: threading.Event) -> dict:
        if threading.current_thread() is not threading.main_thread():
            return {}
        previous = {}
        for sig in (signal.SIGTERM, signal.SIGINT):
            previous[sig] = signal.signal(sig, lambda _signum, _frame: stop.set())
        return previous

    @staticmethod
    def _restore_signal_handlers(previous: dict) -> None:
        for sig, handler in previous.items():
            signal.signal(sig, handler)
