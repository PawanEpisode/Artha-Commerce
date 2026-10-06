"""
Checks that need real concurrent connections or the real query planner, so they run on PostgreSQL (CI uses 16) and are
skipped on the SQLite used for quick local runs. The same rules are covered on any database by the sequential and
re-entrant tests in `test_timer_pipeline.py`.
"""

import threading
import uuid
from datetime import timedelta

import pytest
from django.db import connection, connections

from modules.notifications.domain.enums import JobStatus
from modules.notifications.models import Delivery, Notification, ScheduledJob
from modules.notifications.scheduling import jobs
from modules.notifications.tests.helpers import register
from modules.notifications.tests.timer_bench import FOCUS_END, NOW, USER

postgres_only = pytest.mark.skipif(connection.vendor != "postgresql", reason="needs PostgreSQL")


@postgres_only
@pytest.mark.django_db(transaction=True)
def test_workers_firing_one_job_at_the_same_moment_make_one_delivery(bench, fake_push):
    register(USER)
    timer = bench.start()
    job = ScheduledJob.objects.get(subject_key=str(timer.client_id))
    workers = 6
    gate = threading.Barrier(workers)
    results, errors = [], []

    def worker():
        try:
            gate.wait(timeout=10)
            results.append(jobs.fire_job(job.id, now=FOCUS_END))
        except Exception as exc:  # noqa: BLE001 - reported below
            errors.append(exc)
        finally:
            connections.close_all()  # each thread has its own connection

    threads = [threading.Thread(target=worker) for _ in range(workers)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)

    assert errors == []
    outcomes = sorted(r.outcome.value for r in results)
    assert outcomes == ["ignored"] * (workers - 1) + ["notified"]  # exactly one caller won the claim
    assert len(fake_push.sent) == 1 and Notification.objects.count() == 1 and Delivery.objects.count() == 1
    job.refresh_from_db()
    assert job.status == JobStatus.FIRED and job.attempts == 1


@postgres_only
@pytest.mark.django_db
def test_the_sweep_query_is_served_by_the_partial_index_on_pending_jobs():
    ScheduledJob.objects.bulk_create(
        ScheduledJob(
            user_id=uuid.uuid4(),
            kind="timer_end",
            subject_key=str(uuid.uuid4()),
            expected_version=1,
            fire_at=NOW - timedelta(minutes=i),
            status="pending" if i < 3 else "skipped",
        )
        for i in range(10)
    )
    with connection.cursor() as cursor:
        cursor.execute("SET LOCAL enable_seqscan = off")  # a tiny table would otherwise be scanned
    plan = (
        ScheduledJob.objects.filter(status=JobStatus.PENDING, fire_at__lte=NOW)
        .order_by("fire_at")
        .values_list("id", flat=True)[:50]
        .explain()
    )
    assert "notif_job_due_idx" in plan
