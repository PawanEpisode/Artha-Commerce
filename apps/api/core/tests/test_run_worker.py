"""The always-on worker: limits, signals, grace, crash recovery (real subprocesses) and the health command."""

import json
import os
import signal
import subprocess
import sys
import threading
import time
from datetime import timedelta
from io import StringIO
from pathlib import Path

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection
from django.utils import timezone

from core import jobs
from core.management.commands import worker_health
from core.models import Job

API_DIR = Path(__file__).resolve().parents[2]

WORKER_SCRIPT = """
import os, time, django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()
from django.core.management import call_command
from core import jobs
jobs.register_handler("t.slow", lambda payload: time.sleep(float(payload["s"])) or {"slept": True})
call_command("run_worker", "--sleep", "0.1", "--heartbeat", "0.2")
"""


@pytest.fixture(autouse=True)
def _handlers():
    saved = dict(jobs._handlers)
    jobs.clear_handlers()
    yield
    jobs.clear_handlers()
    jobs._handlers.update(saved)


# --- in-process: arguments and limits ------------------------------------------------------------------------------------


@pytest.mark.django_db
def test_concurrency_flag_caps_a_type_with_a_short_alias():
    jobs.register_handler("notes.ocr", lambda p: None)
    jobs.register_handler("t.light", lambda p: None)
    ocr = [jobs.enqueue("notes.ocr") for _ in range(2)]
    jobs.claim_next(worker="busy elsewhere")  # another worker holds the only OCR slot
    out = StringIO()
    jobs.enqueue("t.light")
    call_command("run_worker", "--once", "--concurrency", "ocr=1", stdout=out)
    assert "Ran 1 job(s)." in out.getvalue()  # only the light job ran
    assert Job.objects.filter(type="notes.ocr", status="queued").count() == 1 and ocr


@pytest.mark.django_db
def test_env_limits_are_read_when_no_flag_is_given(monkeypatch):
    monkeypatch.setenv("WORKER_TYPE_LIMITS", "t.a=0")
    jobs.register_handler("t.a", lambda p: None)
    jobs.enqueue("t.a")
    out = StringIO()
    call_command("run_worker", "--once", stdout=out)
    assert "Ran 0 job(s)." in out.getvalue() and Job.objects.filter(status="queued").count() == 1


@pytest.mark.django_db
def test_bad_limits_are_a_command_error():
    with pytest.raises(CommandError):
        call_command("run_worker", "--once", "--concurrency", "ocr")


@pytest.mark.django_db
def test_forever_mode_runs_jobs_supervised_and_stops_on_sigterm(tmp_path, monkeypatch):
    monkeypatch.setenv("WORKER_LIVENESS_FILE", str(tmp_path / "alive"))
    jobs.register_handler("t.a", lambda p: {"ok": True})
    job = jobs.enqueue("t.a")
    timer = threading.Timer(0.8, lambda: os.kill(os.getpid(), signal.SIGTERM))
    previous = signal.getsignal(signal.SIGTERM)
    timer.start()
    out = StringIO()
    try:
        call_command("run_worker", "--sleep", "0.05", stdout=out)  # returns only because SIGTERM was handled
    finally:
        timer.cancel()
    assert signal.getsignal(signal.SIGTERM) is previous  # the command restores the process's own handler
    text = out.getvalue()
    assert "t.a done" in text and "Stopping on request." in text
    job.refresh_from_db()
    assert job.status == "done" and (tmp_path / "alive").exists()


@pytest.mark.django_db
def test_max_jobs_stops_forever_mode():
    jobs.register_handler("t.a", lambda p: None)
    for _ in range(3):
        jobs.enqueue("t.a")
    out = StringIO()
    call_command("run_worker", "--max-jobs", "2", "--sleep", "0.01", stdout=out)
    assert "Ran 2 job(s)." in out.getvalue() and Job.objects.filter(status="queued").count() == 1


# --- real processes: kill, SIGTERM, grace --------------------------------------------------------------------------------


def _worker_env(tmp_path, **extra):
    s = connection.settings_dict
    url = f"postgres://{s['USER']}:{s['PASSWORD']}@{s['HOST'] or 'localhost'}:{s['PORT'] or 5432}/{s['NAME']}"
    return {**os.environ, "DATABASE_URL": url, "WORKER_LIVENESS_FILE": str(tmp_path / "alive"), **extra}


def _start_worker(tmp_path, **env):
    if connection.vendor != "postgresql":
        pytest.skip("the subprocess worker needs a shared Postgres database")
    return subprocess.Popen(  # noqa: S603 - our own interpreter and a fixed script
        [sys.executable, "-c", WORKER_SCRIPT],
        cwd=API_DIR,
        env=_worker_env(tmp_path, **env),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def _wait_for(predicate, timeout=40.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.1)
    return False


@pytest.mark.django_db(transaction=True)
def test_a_worker_killed_mid_job_loses_nothing_the_job_is_reclaimed(tmp_path):
    job = jobs.enqueue("t.slow", {"s": 60})
    proc = _start_worker(tmp_path)
    try:
        assert _wait_for(lambda: Job.objects.get(pk=job.pk).status == "running"), proc.stderr.read()
        proc.kill()  # SIGKILL: no cleanup of any kind
        proc.wait(timeout=10)
    finally:
        if proc.poll() is None:
            proc.kill()
    job.refresh_from_db()
    assert job.status == "running" and job.attempts == 1  # left behind, exactly as a crash would
    assert jobs.claim_next(now=timezone.now() + timedelta(minutes=1)) is None  # still inside the visibility timeout
    again = jobs.claim_next(worker="survivor", now=timezone.now() + jobs.VISIBILITY_TIMEOUT + timedelta(seconds=5))
    assert again.pk == job.pk and again.attempts == 2 and again.locked_by == "survivor"


@pytest.mark.django_db(transaction=True)
def test_sigterm_lets_the_current_job_finish_then_exits_zero(tmp_path):
    job = jobs.enqueue("t.slow", {"s": 1.5})
    proc = _start_worker(tmp_path, WORKER_SHUTDOWN_GRACE_SECONDS="30")
    try:
        assert _wait_for(lambda: Job.objects.get(pk=job.pk).status == "running"), proc.stderr.read()
        proc.send_signal(signal.SIGTERM)
        code = proc.wait(timeout=40)
    finally:
        if proc.poll() is None:
            proc.kill()
    job.refresh_from_db()
    assert code == 0 and job.status == "done" and job.result == {"slept": True}


@pytest.mark.django_db(transaction=True)
def test_sigterm_past_the_grace_period_requeues_the_job_and_exits_zero(tmp_path):
    job = jobs.enqueue("t.slow", {"s": 120})
    proc = _start_worker(tmp_path, WORKER_SHUTDOWN_GRACE_SECONDS="1")
    try:
        assert _wait_for(lambda: Job.objects.get(pk=job.pk).status == "running"), proc.stderr.read()
        proc.send_signal(signal.SIGTERM)
        code = proc.wait(timeout=40)
    finally:
        if proc.poll() is None:
            proc.kill()
    job.refresh_from_db()
    assert code == 0
    assert (job.status, job.attempts, job.locked_by) == ("queued", 0, "")  # handed back, attempt refunded


@pytest.mark.django_db(transaction=True)
def test_a_long_job_keeps_its_lock_fresh_with_heartbeats(tmp_path):
    job = jobs.enqueue("t.slow", {"s": 2.5})
    proc = _start_worker(tmp_path)  # heartbeat every 0.2 s in the script
    try:
        assert _wait_for(lambda: Job.objects.get(pk=job.pk).status == "running"), proc.stderr.read()
        first = Job.objects.get(pk=job.pk).locked_at
        assert _wait_for(lambda: Job.objects.get(pk=job.pk).locked_at != first, timeout=10)
        assert _wait_for(lambda: Job.objects.get(pk=job.pk).status == "done", timeout=20)
        proc.send_signal(signal.SIGTERM)
        assert proc.wait(timeout=20) == 0
    finally:
        if proc.poll() is None:
            proc.kill()


# --- worker_health --------------------------------------------------------------------------------------------------------


def _health(*args):
    out = StringIO()
    try:
        call_command("worker_health", *args, stdout=out)
        code = 0
    except SystemExit as exc:
        code = exc.code
    return code, json.loads(out.getvalue())


@pytest.mark.django_db
def test_health_reports_queue_depth_and_age_per_type_without_payloads(tmp_path, monkeypatch):
    monkeypatch.setenv("WORKER_LIVENESS_FILE", str(tmp_path / "alive"))
    jobs.enqueue("t.a", {"secret": "never shown"})
    jobs.enqueue("t.a")
    old = jobs.enqueue("t.b")
    Job.objects.filter(pk=old.pk).update(run_after=timezone.now() - timedelta(minutes=30))
    jobs.enqueue("t.later", run_after=timezone.now() + timedelta(hours=1))
    running = jobs.enqueue("t.c")
    claimed = jobs.claim_next(types=["t.c"])
    Job.objects.filter(pk=claimed.pk).update(locked_at=timezone.now() - timedelta(minutes=10))
    code, report = _health()
    assert code == 0 and report["ok"] is True and report["db"]["ok"] is True
    queued = report["jobs"]["queued"]
    assert queued["t.a"]["depth"] == 2 and queued["t.b"]["oldest_age_s"] >= 1790 and "t.later" not in queued
    assert report["jobs"]["running"] == 1 and report["jobs"]["stale_running"] == 1
    assert "backlog:t.b" in report["warnings"] and "stale_running_jobs" in report["warnings"]
    assert "never shown" not in json.dumps(report) and running


@pytest.mark.django_db
def test_health_requires_a_live_worker_when_asked(tmp_path, monkeypatch):
    alive = tmp_path / "alive"
    monkeypatch.setenv("WORKER_LIVENESS_FILE", str(alive))
    code, report = _health("--require-worker")
    assert code == 1 and "worker_not_alive" in report["problems"] and report["worker"]["heartbeat_age_s"] is None
    jobs.touch_liveness(str(alive))
    code, report = _health("--require-worker")
    assert code == 0 and report["worker"]["heartbeat_age_s"] < 5
    old = time.time() - 600
    os.utime(alive, (old, old))
    assert _health("--require-worker")[0] == 1
    assert _health()[0] == 0  # without the flag a missing or old heartbeat is only information


@pytest.mark.django_db
def test_health_fails_when_the_database_is_unreachable(monkeypatch):
    monkeypatch.setattr(worker_health.Command, "_database", staticmethod(lambda: {"ok": False, "latency_ms": None}))
    code, report = _health()
    assert code == 1 and report["problems"] == ["database_unreachable"] and "jobs" not in report


@pytest.mark.django_db
def test_health_checks_required_tools(monkeypatch, tmp_path):
    monkeypatch.setenv("WORKER_LIVENESS_FILE", str(tmp_path / "alive"))
    monkeypatch.setattr(worker_health, "tesseract_status", lambda: {"ok": False, "version": None, "langs": []})
    code, report = _health("--require-tools", "tesseract")
    assert code == 1 and report["problems"] == ["tesseract_missing"]
    monkeypatch.setattr(
        worker_health, "tesseract_status", lambda: {"ok": True, "version": "5.3.4", "langs": ["eng", "hin"]}
    )
    assert _health("--require-tools", "tesseract")[0] == 0


@pytest.mark.django_db
def test_health_clamd_is_optional_until_required(monkeypatch, settings, tmp_path):
    monkeypatch.setenv("WORKER_LIVENESS_FILE", str(tmp_path / "alive"))
    settings.MEDIA_SCANNER = "null"
    code, report = _health("--require-tools", "clamd")
    assert code == 1 and report["tools"]["clamd"] == {"configured": False, "ok": None}
    settings.MEDIA_SCANNER = "clamd"
    settings.CLAMD_HOST, settings.CLAMD_PORT, settings.CLAMD_SOCKET = "127.0.0.1", 1, ""  # nothing listens there
    code, report = _health("--require-tools", "clamd")
    assert code == 1 and report["tools"]["clamd"] == {"configured": True, "ok": False}


def test_clamd_ping_talks_the_real_protocol(settings, tmp_path):
    import socket

    sock_path = str(tmp_path / "clamd.sock")
    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(sock_path)
    server.listen(1)

    def serve():
        conn, _ = server.accept()
        with conn:
            assert conn.recv(16) == b"zPING\0"
            conn.sendall(b"PONG\0")

    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    settings.MEDIA_SCANNER, settings.CLAMD_SOCKET = "clamd", sock_path
    try:
        assert worker_health.clamd_status() == {"configured": True, "ok": True}
    finally:
        thread.join(timeout=5)
        server.close()
