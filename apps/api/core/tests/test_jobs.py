"""The durable job queue: dedupe, claim order, retries with backoff, reclaiming a dead worker, the worker command."""

from datetime import timedelta
from io import StringIO

import pytest
from django.core.management import call_command
from django.utils import timezone

from core import jobs
from core.models import Job

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _handlers():
    saved = dict(jobs._handlers)
    jobs.clear_handlers()
    yield
    jobs.clear_handlers()
    jobs._handlers.update(saved)


def test_enqueue_dedupes_active_jobs_by_key():
    a = jobs.enqueue("t.a", {"n": 1}, dedupe_key="k")
    b = jobs.enqueue("t.a", {"n": 2}, dedupe_key="k")
    assert a.pk == b.pk and Job.objects.count() == 1
    jobs.complete(jobs.claim_next())
    assert jobs.enqueue("t.a", dedupe_key="k").pk != a.pk  # finished: a new run is allowed


def test_once_dedupes_even_after_the_job_finished():
    first = jobs.enqueue("t.a", dedupe_key="day:2026-10-07", once=True)
    jobs.complete(jobs.claim_next())
    assert jobs.enqueue("t.a", dedupe_key="day:2026-10-07", once=True).pk == first.pk
    assert Job.objects.count() == 1


def test_claim_order_is_priority_then_age_and_respects_run_after_and_types():
    now = timezone.now()
    low = jobs.enqueue("t.a", priority=0)
    high = jobs.enqueue("t.b", priority=5)
    jobs.enqueue("t.a", run_after=now + timedelta(hours=1))
    assert jobs.claim_next(types=["t.a"]).pk == low.pk
    assert jobs.claim_next().pk == high.pk
    assert jobs.claim_next() is None  # the third is not due yet


def test_a_claim_marks_the_job_running_and_counts_the_attempt():
    jobs.enqueue("t.a")
    job = jobs.claim_next(worker="w1")
    assert (job.status, job.attempts, job.locked_by) == ("running", 1, "w1")
    assert jobs.claim_next() is None  # not claimable twice


def test_a_dead_workers_job_is_reclaimed_after_the_visibility_timeout():
    jobs.enqueue("t.a")
    job = jobs.claim_next()
    assert jobs.claim_next(now=timezone.now() + timedelta(minutes=1)) is None
    again = jobs.claim_next(now=timezone.now() + jobs.VISIBILITY_TIMEOUT + timedelta(seconds=1))
    assert again.pk == job.pk and again.attempts == 2


def test_a_reclaimed_job_out_of_attempts_is_closed_as_failed():
    jobs.enqueue("t.a", max_attempts=1)
    job = jobs.claim_next()
    assert jobs.claim_next(now=timezone.now() + jobs.VISIBILITY_TIMEOUT + timedelta(seconds=1)) is None
    job.refresh_from_db()
    assert job.status == "failed" and "Gave up" in job.last_error


def test_failures_back_off_and_end_as_failed():
    jobs.enqueue("t.a", max_attempts=3)
    waits = []
    for _ in range(3):
        job = jobs.claim_next(now=timezone.now() + timedelta(hours=3))
        jobs.fail(job, "boom")
        job.refresh_from_db()
        waits.append(job.run_after - timezone.now())
    assert job.status == "failed" and job.last_error == "boom"
    assert waits[0] < waits[1] + timedelta(hours=3)  # the first retry is the shortest delay; later runs end


def test_run_job_records_results_and_never_raises():
    jobs.register_handler("t.ok", lambda payload: {"got": payload["x"]})
    jobs.register_handler("t.bad", lambda payload: 1 / 0)
    ok, bad = jobs.enqueue("t.ok", {"x": 3}), jobs.enqueue("t.bad", max_attempts=1)
    assert jobs.run_job(jobs.claim_next(types=["t.ok"])) == "done"
    assert jobs.run_job(jobs.claim_next(types=["t.bad"])) == "failed"
    ok.refresh_from_db(), bad.refresh_from_db()
    assert ok.result == {"got": 3} and "ZeroDivisionError" in bad.last_error


def test_an_unknown_type_fails_without_retry():
    jobs.enqueue("t.nobody")
    assert jobs.run_job(jobs.claim_next()) == "failed"


def test_registering_twice_is_fine_but_a_clash_is_an_error():
    def fn(payload):
        return None

    jobs.register_handler("t.a", fn)
    jobs.register_handler("t.a", fn)
    with pytest.raises(ValueError):
        jobs.register_handler("t.a", lambda p: None)
    assert jobs.handler_types() == ["t.a"]


def test_run_pending_stops_at_max_jobs_and_budget():
    jobs.register_handler("t.a", lambda p: None)
    for _ in range(5):
        jobs.enqueue("t.a")
    assert jobs.run_pending(max_jobs=2) == 2
    assert jobs.run_pending(budget_seconds=0) == 0
    assert jobs.run_pending() == 3


def test_prune_removes_only_old_finished_jobs():
    jobs.enqueue("t.a"), jobs.enqueue("t.a")
    done = jobs.claim_next()
    jobs.complete(done)
    Job.objects.filter(pk=done.pk).update(finished_at=timezone.now() - timedelta(days=30))
    assert jobs.prune_finished() == 1 and Job.objects.count() == 1


def test_describe_leaves_the_payload_out():
    job = jobs.enqueue("t.a", {"secret": "x"})
    assert "secret" not in str(jobs.describe(job))


def test_the_worker_command_drains_the_queue_once():
    jobs.register_handler("t.a", lambda p: {"ok": True})
    for _ in range(3):
        jobs.enqueue("t.a")
    out = StringIO()
    call_command("run_worker", "--once", stdout=out)
    assert "Ran 3 job(s)." in out.getvalue() and Job.objects.filter(status="done").count() == 3


def test_the_worker_command_filters_types_and_honours_max_jobs():
    jobs.register_handler("t.a", lambda p: None)
    jobs.register_handler("t.b", lambda p: None)
    jobs.enqueue("t.a"), jobs.enqueue("t.a"), jobs.enqueue("t.b")
    out = StringIO()
    call_command("run_worker", "--once", "--types", "t.b", stdout=out)
    assert "Ran 1 job(s)." in out.getvalue() and Job.objects.filter(status="queued").count() == 2
    call_command("run_worker", "--once", "--max-jobs", "1", stdout=StringIO())
    assert Job.objects.filter(status="queued").count() == 1
