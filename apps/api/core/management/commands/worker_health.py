"""
Health of the worker and the queue, as JSON, with exit code 0 (healthy) or 1. The container HEALTHCHECK runs

    python manage.py worker_health --require-worker --require-tools tesseract,clamd

Checks: the database answers; the worker loop touched its liveness file recently (`--require-worker`); queue depth and the
age of the oldest due job per type; running jobs whose lock has not been refreshed; the Tesseract and clamd tools. Only the
database, a required worker and required tools make the exit code 1; queue age and stale locks are reported as warnings
because a backlog is a capacity question, not a dead container. No payloads or user data are ever printed.
"""

import json
import os
import shutil
import socket
import subprocess
import time

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import DatabaseError, connection
from django.db.models import Count, Min
from django.utils import timezone

from core import jobs
from core.models import Job

HEARTBEAT_MAX_AGE = 120.0  # seconds without the loop touching its file means it is wedged
QUEUE_WARN_AGE = 15 * 60.0


def _age(moment) -> float | None:
    return None if moment is None else round((timezone.now() - moment).total_seconds(), 1)


def clamd_status() -> dict:
    """PING the clamd daemon with the same settings the media scanner uses. `configured` is False when the null scanner is on."""
    if getattr(settings, "MEDIA_SCANNER", "null") != "clamd":
        return {"configured": False, "ok": None}
    sock_path = getattr(settings, "CLAMD_SOCKET", "") or ""
    host, port = getattr(settings, "CLAMD_HOST", ""), int(getattr(settings, "CLAMD_PORT", 3310) or 3310)
    try:
        if sock_path:
            client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            client.settimeout(3)
            client.connect(sock_path)
        else:
            client = socket.create_connection((host, port), timeout=3)
        with client:
            client.sendall(b"zPING\0")
            reply = client.recv(16)
        return {"configured": True, "ok": reply.strip(b"\0\n ") == b"PONG"}
    except OSError:
        return {"configured": True, "ok": False}


def tesseract_status() -> dict:
    exe = shutil.which("tesseract")
    if exe is None:
        return {"ok": False, "version": None, "langs": []}
    try:
        version = subprocess.run([exe, "--version"], capture_output=True, text=True, timeout=10, check=False)
        langs = subprocess.run([exe, "--list-langs"], capture_output=True, text=True, timeout=10, check=False)
    except (OSError, subprocess.SubprocessError):
        return {"ok": False, "version": None, "langs": []}
    first = (version.stdout or version.stderr).splitlines()[0] if (version.stdout or version.stderr) else ""
    names = [line.strip() for line in langs.stdout.splitlines()[1:] if line.strip()]
    return {"ok": True, "version": first.replace("tesseract ", ""), "langs": names}


class Command(BaseCommand):
    help = "Print worker and queue health as JSON; exit 1 when unhealthy."

    def add_arguments(self, parser):
        parser.add_argument("--require-worker", action="store_true", help="Fail when the worker loop is not alive.")
        parser.add_argument(
            "--require-tools", default="", help="Comma list of tools that must be present: tesseract,clamd."
        )

    def handle(self, *args, require_worker=False, require_tools="", **options):
        report: dict = {"time": timezone.now().isoformat(timespec="seconds"), "problems": [], "warnings": []}
        problems: list[str] = report["problems"]

        report["db"] = self._database()
        if not report["db"]["ok"]:
            problems.append("database_unreachable")
        else:
            report["jobs"] = self._queue(report["warnings"])

        liveness = os.environ.get("WORKER_LIVENESS_FILE", jobs.LIVENESS_FILE_DEFAULT)
        try:
            beat_age = round(time.time() - os.stat(liveness).st_mtime, 1)
        except OSError:
            beat_age = None
        report["worker"] = {"heartbeat_age_s": beat_age}
        if require_worker and (beat_age is None or beat_age > HEARTBEAT_MAX_AGE):
            problems.append("worker_not_alive")

        wanted = {t.strip() for t in require_tools.split(",") if t.strip()}
        report["tools"] = {"tesseract": tesseract_status(), "clamd": clamd_status()}
        if "tesseract" in wanted and not report["tools"]["tesseract"]["ok"]:
            problems.append("tesseract_missing")
        if "clamd" in wanted and report["tools"]["clamd"]["ok"] is not True:
            problems.append("clamd_unavailable")

        report["ok"] = not problems
        self.stdout.write(json.dumps(report, sort_keys=True))
        if problems:
            raise SystemExit(1)

    @staticmethod
    def _database() -> dict:
        started = time.monotonic()
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
        except DatabaseError:
            return {"ok": False, "latency_ms": None}
        return {"ok": True, "latency_ms": round((time.monotonic() - started) * 1000, 1)}

    @staticmethod
    def _queue(warnings: list[str]) -> dict:
        now = timezone.now()
        due = Job.objects.filter(status=Job.Status.QUEUED, run_after__lte=now)
        queued = {
            row["type"]: {"depth": row["depth"], "oldest_age_s": _age(row["oldest"])}
            for row in due.values("type").annotate(depth=Count("id"), oldest=Min("run_after")).order_by("type")
        }
        running = Job.objects.filter(status=Job.Status.RUNNING)
        stale = running.filter(locked_at__lt=now - jobs.VISIBILITY_TIMEOUT).count()
        oldest_lock = running.aggregate(oldest=Min("locked_at"))["oldest"]
        for job_type, info in queued.items():
            if info["oldest_age_s"] is not None and info["oldest_age_s"] > QUEUE_WARN_AGE:
                warnings.append(f"backlog:{job_type}")
        if stale:
            warnings.append("stale_running_jobs")
        return {
            "queued": queued,
            "running": running.count(),
            "stale_running": stale,
            "oldest_running_heartbeat_age_s": _age(oldest_lock),
        }
