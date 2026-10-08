"""The durable job queue: dedupe, claim order, retries with backoff, reclaiming a dead worker, the worker command."""

import threading
import time
from datetime import timedelta
from io import StringIO

import pytest
from django.core.management import call_command
from django.db import connection
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


def test_a_job_the_queue_closes_itself_tells_its_gave_up_handler():
    seen = []
    jobs.register_gave_up_handler("t.gone", seen.append)
    try:
        jobs.enqueue("t.gone", {"charged": 5}, max_attempts=1)
        jobs.claim_next()
        assert jobs.claim_next(now=timezone.now() + jobs.VISIBILITY_TIMEOUT + timedelta(seconds=1)) is None
        assert seen == [{"charged": 5}]
    finally:
        jobs._gave_up_handlers.pop("t.gone", None)


def test_a_failing_gave_up_handler_never_stops_the_queue():
    jobs.register_gave_up_handler("t.gone2", lambda payload: 1 / 0)
    try:
        jobs.enqueue("t.gone2", max_attempts=1)
        jobs.enqueue("t.next")
        jobs.claim_next(types=["t.gone2"])
        job = jobs.claim_next(now=timezone.now() + jobs.VISIBILITY_TIMEOUT + timedelta(seconds=1))
        assert job is not None and job.type == "t.next"
    finally:
        jobs._gave_up_handlers.pop("t.gone2", None)


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


# --- worker runtime: heartbeat, requeue, per-type limits, supervised runs ------------------------------------------------


def test_heartbeat_refreshes_the_lock_so_a_healthy_job_is_not_reclaimed():
    jobs.enqueue("t.a")
    job = jobs.claim_next(worker="w1")
    Job.objects.filter(pk=job.pk).update(locked_at=timezone.now() - timedelta(minutes=4))
    assert jobs.heartbeat(job) is True
    later = timezone.now() + timedelta(minutes=2)  # 6 minutes after the original lock, 2 after the heartbeat
    assert jobs.claim_next(now=later) is None
    job.refresh_from_db()
    assert job.status == "running" and timezone.now() - job.locked_at < timedelta(seconds=5)


def test_heartbeat_reports_a_lost_lock():
    jobs.enqueue("t.a")
    job = jobs.claim_next(worker="w1")
    taken = jobs.claim_next(now=timezone.now() + jobs.VISIBILITY_TIMEOUT + timedelta(seconds=1), worker="w2")
    assert taken.pk == job.pk
    assert jobs.heartbeat(job) is False  # w1 no longer owns it
    jobs.complete(taken)
    assert jobs.heartbeat(taken) is False  # finished jobs are not running


def test_a_handler_can_heartbeat_without_a_job_argument():
    seen = []

    def long_handler(payload):
        seen.append(jobs.heartbeat())
        return None

    jobs.register_handler("t.long", long_handler)
    jobs.enqueue("t.long")
    jobs.run_job(jobs.claim_next())
    assert seen == [True] and jobs.heartbeat() is False  # outside a handler there is no current job


def test_requeue_hands_the_job_back_and_refunds_the_attempt():
    jobs.enqueue("t.a")
    job = jobs.claim_next(worker="w1")
    assert job.attempts == 1 and jobs.requeue(job) is True
    job.refresh_from_db()
    assert (job.status, job.attempts, job.locked_by, job.locked_at) == ("queued", 0, "", None)
    claimed = jobs.claim_next(worker="w2")
    assert claimed.pk == job.pk
    assert jobs.requeue(job) is False  # `job` still describes w1's old lock; w2 owns it now
    jobs.complete(claimed)
    assert jobs.requeue(claimed) is False  # done jobs stay done


def test_parse_type_limits():
    assert jobs.parse_type_limits("notes.ocr=1, notes.export_pdf=2") == {"notes.ocr": 1, "notes.export_pdf": 2}
    assert jobs.parse_type_limits("") == {} and jobs.parse_type_limits(None) == {}
    assert jobs.parse_type_limits("export=1", {"export": ("a.x", "a.y")}) == {"a.x": 1, "a.y": 1}
    for bad in ("ocr", "ocr=", "ocr=x", "=1", "ocr=-1"):
        with pytest.raises(ValueError):
            jobs.parse_type_limits(bad)


def test_a_type_at_its_cap_is_skipped_but_other_types_still_run():
    ocr = [jobs.enqueue("t.ocr") for _ in range(3)]
    other = jobs.enqueue("t.light", priority=-1)
    limits = {"t.ocr": 1}
    first = jobs.claim_next(limits=limits)
    assert first.pk == ocr[0].pk
    second = jobs.claim_next(limits=limits)  # the other two OCR jobs are blocked, the light one is next
    assert second.pk == other.pk
    assert jobs.claim_next(limits=limits) is None
    jobs.complete(first)
    assert jobs.claim_next(limits=limits).pk == ocr[1].pk  # a slot freed up
    assert jobs.claim_next().pk == ocr[2].pk  # no limits given: no cap


def test_a_cap_of_zero_never_claims_that_type_and_the_cap_respects_the_types_filter():
    jobs.enqueue("t.ocr")
    assert jobs.claim_next(limits={"t.ocr": 0}) is None
    assert jobs.claim_next(types=["t.light"], limits={"t.ocr": 0}) is None


def test_a_crashed_job_is_reclaimable_even_when_its_type_is_capped_at_one():
    jobs.enqueue("t.ocr")
    dead = jobs.claim_next(worker="dead", limits={"t.ocr": 1})
    assert jobs.claim_next(limits={"t.ocr": 1}) is None  # a healthy running job holds the only slot
    later = timezone.now() + jobs.VISIBILITY_TIMEOUT + timedelta(seconds=1)
    again = jobs.claim_next(worker="live", now=later, limits={"t.ocr": 1})
    assert again.pk == dead.pk and again.attempts == 2 and again.locked_by == "live"


def test_the_same_priority_ordering_holds_under_limits():
    low = jobs.enqueue("t.a", priority=0)
    high = jobs.enqueue("t.b", priority=9)
    assert jobs.claim_next(limits={"t.a": 5, "t.b": 5}).pk == high.pk
    assert jobs.claim_next(limits={"t.a": 5, "t.b": 5}).pk == low.pk


def test_supervised_run_records_the_outcome_and_logs_one_line_without_the_payload(caplog):
    jobs.register_handler("t.ok", lambda payload: {"n": 1})
    jobs.register_handler("t.bad", lambda payload: 1 / 0)
    ok = jobs.enqueue("t.ok", {"secret": "do-not-log"})
    bad = jobs.enqueue("t.bad", max_attempts=1)
    with caplog.at_level("INFO", logger="core.jobs"):
        assert jobs.run_supervised(jobs.claim_next(types=["t.ok"]), poll=0.01) == "done"
        assert jobs.run_supervised(jobs.claim_next(types=["t.bad"]), poll=0.01) == "failed"
    ok.refresh_from_db(), bad.refresh_from_db()
    assert ok.result == {"n": 1} and "ZeroDivisionError" in bad.last_error
    lines = [r.getMessage() for r in caplog.records if r.getMessage().startswith("job type=")]
    assert len(lines) == 2 and "type=t.ok status=done" in lines[0] and "duration_ms=" in lines[0]
    assert "do-not-log" not in caplog.text


def test_supervised_run_keeps_the_lock_fresh_while_a_slow_handler_runs():
    release = threading.Event()
    jobs.register_handler("t.slow", lambda payload: release.wait(5) and None)
    jobs.enqueue("t.slow")
    job = jobs.claim_next(worker="w1")
    Job.objects.filter(pk=job.pk).update(locked_at=timezone.now() - timedelta(minutes=4))
    beats = []
    original = jobs.heartbeat

    def spy(j=None):
        beats.append(original(j))
        release.set()  # let the handler finish after the first heartbeat
        return beats[-1]

    jobs.heartbeat = spy
    try:
        assert jobs.run_supervised(job, heartbeat_interval=0.05, poll=0.01) == "done"
    finally:
        jobs.heartbeat = original
    assert beats and beats[0] is True


def test_supervised_run_requeues_after_the_grace_period_when_asked_to_stop():
    release = threading.Event()
    jobs.register_handler("t.stuck", lambda payload: release.wait(10))
    jobs.enqueue("t.stuck")
    job = jobs.claim_next(worker="w1")
    stop = threading.Event()
    stop.set()
    started = time.monotonic()
    try:
        status = jobs.run_supervised(job, stop=stop, grace=0.2, poll=0.02)
    finally:
        release.set()
    assert status == "queued" and time.monotonic() - started < 3
    job.refresh_from_db()
    assert (job.status, job.attempts, job.locked_by) == ("queued", 0, "")


def test_supervised_run_lets_a_job_finish_inside_the_grace_period():
    jobs.register_handler("t.quick", lambda payload: time.sleep(0.15) or {"ok": True})
    jobs.enqueue("t.quick")
    stop = threading.Event()
    stop.set()
    assert jobs.run_supervised(jobs.claim_next(), stop=stop, grace=5, poll=0.02) == "done"


def test_touch_liveness_writes_a_file_and_swallows_errors(tmp_path):
    marker = tmp_path / "alive"
    jobs.touch_liveness(str(marker))
    assert marker.exists()
    jobs.touch_liveness(str(tmp_path / "missing-dir" / "alive"))  # must not raise


@pytest.mark.django_db(transaction=True, serialized_rollback=True)
def test_concurrent_claims_never_exceed_a_cap_of_two():
    if connection.vendor != "postgresql":
        pytest.skip("advisory locks and SKIP LOCKED need Postgres")
    for _ in range(12):
        jobs.enqueue("t.ocr")
    claimed, errors = [], []
    barrier = threading.Barrier(8)

    def worker(n):
        try:
            barrier.wait(timeout=10)
            job = jobs.claim_next(worker=f"w{n}", limits={"t.ocr": 2})
            if job:
                claimed.append(job.pk)
        except Exception as exc:  # noqa: BLE001 - surfaced by the assertion below
            errors.append(exc)
        finally:
            from django.db import connections

            connections.close_all()

    threads = [threading.Thread(target=worker, args=(n,)) for n in range(8)]
    [t.start() for t in threads]
    [t.join(timeout=30) for t in threads]
    assert not errors, errors
    assert len(claimed) == 2 == Job.objects.filter(status="running").count()
