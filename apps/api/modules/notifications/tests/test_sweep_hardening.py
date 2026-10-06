"""W2.7 sweep steps: the delivery check that raises `push_slo_breach` (FR-N23) and the nightly prune (FR-N24)."""

import logging
import uuid
from datetime import UTC, datetime, timedelta

import pytest

from modules.notifications.domain.enums import JobStatus
from modules.notifications.models import Delivery, Notification, ScheduledJob
from modules.notifications.scheduling import sweep

pytestmark = pytest.mark.django_db
NOW = datetime(2026, 10, 6, 12, 0, tzinfo=UTC)
USER = uuid.uuid4()


def notification(**kw) -> Notification:
    return Notification.objects.create(
        user_id=USER,
        category="timer",
        event="timer_end",
        dedupe_key=f"k:{uuid.uuid4().hex}",
        title="t",
        body="b",
        deep_link="/app/focus",
        priority=0,
        **kw,
    )


def attempt(status="sent", minutes_ago=3, lateness_ms=1000, channel="push", suppress_reason=None) -> Delivery:
    return Delivery.objects.create(
        notification=notification(),
        user_id=USER,
        channel=channel,
        status=status,
        suppress_reason=suppress_reason,
        lateness_ms=lateness_ms if status == "sent" else None,
        attempted_at=NOW - timedelta(minutes=minutes_ago),
    )


def breaches(caplog):
    return [r for r in caplog.records if r.getMessage().startswith("push_slo_breach")]


def test_a_healthy_quarter_hour_logs_no_breach(caplog):
    for _ in range(10):
        attempt()
    caplog.set_level(logging.INFO)
    sweep.run_sweep(now=NOW)
    assert not breaches(caplog)


def test_failures_in_the_last_15_minutes_log_one_error_with_the_numbers(caplog):
    for _ in range(8):
        attempt()
    for _ in range(2):
        attempt("failed")
    caplog.set_level(logging.INFO)
    sweep.run_sweep(now=NOW)
    (line,) = breaches(caplog)
    assert line.levelno == logging.ERROR
    assert line.push["attempts"] == 10 and line.push["accepted_ratio"] == 0.8 and line.push["ratio_breached"] is True
    assert "p95_ms=1000" in line.getMessage() and "window_minutes=15" in line.getMessage()


def test_slow_pushes_log_a_lateness_breach(caplog):
    for _ in range(10):
        attempt(lateness_ms=7000)
    caplog.set_level(logging.INFO)
    sweep.run_sweep(now=NOW)
    (line,) = breaches(caplog)
    assert line.push["lateness_breached"] is True and line.push["ratio_breached"] is False


def test_attempts_older_than_15_minutes_are_not_judged(caplog):
    for _ in range(10):
        attempt("failed", minutes_ago=16)
    caplog.set_level(logging.INFO)
    sweep.run_sweep(now=NOW)
    assert not breaches(caplog)


def test_suppressed_rows_and_other_channels_are_not_attempts(caplog):
    for _ in range(10):
        attempt("suppressed", suppress_reason="cap")
        attempt("failed", channel="email")
    caplog.set_level(logging.INFO)
    sweep.run_sweep(now=NOW)
    assert not breaches(caplog)


def test_a_failing_check_does_not_stop_the_sweep(monkeypatch, caplog):
    def boom(*args, **kwargs):
        raise RuntimeError("database hiccup with secret-looking text")

    monkeypatch.setattr(sweep, "push_slo_counts", boom)
    caplog.set_level(logging.INFO)
    run = sweep.run_sweep(now=NOW)
    assert run.failed == 0
    (failed,) = [r for r in caplog.records if r.getMessage().startswith("sweep_step_failed")]
    assert "error_type=RuntimeError" in failed.getMessage() and "secret-looking" not in failed.getMessage()
    assert any(r.getMessage().startswith("sweep_run") for r in caplog.records)


def old_notification():
    n = notification()
    Notification.objects.filter(id=n.id).update(created_at=NOW - timedelta(days=200))
    return n


def test_the_prune_runs_in_its_night_window_only():
    old_notification()
    sweep.run_sweep(now=NOW)  # midday
    assert Notification.objects.count() == 1
    sweep.run_sweep(now=NOW.replace(hour=21, minute=29))
    assert Notification.objects.count() == 1
    sweep.run_sweep(now=NOW.replace(hour=21, minute=31))
    assert Notification.objects.count() == 0


def test_the_prune_stops_after_the_window():
    old_notification()
    sweep.run_sweep(now=NOW.replace(hour=21, minute=40))
    assert Notification.objects.count() == 1


def test_the_prune_leaves_pending_jobs_alone():
    stale = ScheduledJob.objects.create(
        user_id=USER, kind="timer_end", subject_key="x", fire_at=NOW - timedelta(days=60), status=JobStatus.PENDING
    )
    sweep.run_sweep(now=NOW.replace(hour=21, minute=31), max_jobs=0)
    assert ScheduledJob.objects.filter(id=stale.id).exists()
