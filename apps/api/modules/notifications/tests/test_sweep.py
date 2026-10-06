"""The per-minute safety net: it fires overdue jobs within bounds, never twice, and logs what it did."""

import logging
import uuid
from datetime import timedelta

import pytest

from modules.notifications import handlers
from modules.notifications.domain.enums import JobKind, JobStatus, SkipReason
from modules.notifications.errors import TransientJobError
from modules.notifications.models import Notification, ScheduledJob
from modules.notifications.scheduling import jobs, sweep
from modules.notifications.tests.helpers import register
from modules.notifications.tests.timer_bench import FOCUS_END, NOW, USER

pytestmark = pytest.mark.django_db
LATE = FOCUS_END + timedelta(minutes=1)  # a minute after a round ended: well past the grace period


class Gone:
    """A stand-in handler that judges every job gone, so these tests are about the sweep and not about timers."""

    def event_key(self, job):
        return "timer_end"

    def judge(self, job, now):
        return handlers.Skip(SkipReason.GONE)


@pytest.fixture
def stub_handler():
    handlers.register(JobKind.TIMER_END, Gone())
    yield
    handlers.register_defaults()


def make_job(seconds_late=60, **kwargs) -> ScheduledJob:
    return ScheduledJob.objects.create(
        user_id=kwargs.pop("user_id", uuid.uuid4()),
        kind="timer_end",
        subject_key=str(uuid.uuid4()),
        expected_version=1,
        fire_at=NOW - timedelta(seconds=seconds_late),
        **kwargs,
    )


def statuses():
    return sorted(ScheduledJob.objects.values_list("status", flat=True))


def test_it_fires_overdue_jobs_and_leaves_the_rest(stub_handler):
    due, soon, future = make_job(120), make_job(5), make_job(-600)  # 2 min late, 5 s late (in the grace), 10 min ahead
    run = sweep.run_sweep(now=NOW)
    assert (run.fired, run.skipped, run.failed, run.more) == (0, 1, 0, False)
    assert ScheduledJob.objects.get(pk=due.pk).status == JobStatus.SKIPPED
    assert ScheduledJob.objects.get(pk=soon.pk).status == JobStatus.PENDING  # the queue still has its own few seconds
    assert ScheduledJob.objects.get(pk=future.pk).status == JobStatus.PENDING


def test_it_goes_oldest_first(stub_handler, monkeypatch):
    order = []
    real = jobs.fire_job
    monkeypatch.setattr(jobs, "fire_job", lambda job_id, now=None: order.append(job_id) or real(job_id, now=now))
    newest, oldest, middle = make_job(30), make_job(900), make_job(300)
    sweep.run_sweep(now=NOW)
    assert order == [oldest.id, middle.id, newest.id]


def test_it_fires_the_job_whose_queue_message_never_arrived_and_the_student_gets_the_push(bench, fake_queue, fake_push):
    register(USER)
    fake_queue.fail_with = RuntimeError("qstash is down")  # the publish at the round's start failed
    bench.start()
    fake_queue.fail_with = None
    run = sweep.run_sweep(now=LATE - timedelta(seconds=30))  # 30 s after the end
    assert (run.fired, run.skipped) == (1, 0) and len(fake_push.sent) == 1
    assert Notification.objects.get().title == "Round 1 done"


def test_a_second_run_finds_nothing_left(stub_handler):
    make_job()
    assert sweep.run_sweep(now=NOW).skipped == 1
    again = sweep.run_sweep(now=NOW)
    assert (again.fired, again.skipped, again.failed, again.more) == (0, 0, 0, False)


def test_one_run_handles_at_most_the_job_bound_and_says_there_is_more(stub_handler):
    for i in range(7):
        make_job(100 + i)
    run = sweep.run_sweep(now=NOW, max_jobs=5)
    assert (run.handled, run.more) == (5, True) and statuses().count("pending") == 2
    rest = sweep.run_sweep(now=NOW, max_jobs=5)  # the leftovers run next minute
    assert (rest.handled, rest.more) == (2, False) and statuses().count("pending") == 0


def test_the_default_bounds_are_the_prds_200_jobs_and_20_seconds():
    assert (sweep.MAX_JOBS, sweep.MAX_SECONDS) == (200, 20.0)


def test_one_run_stops_at_the_time_bound_and_says_there_is_more(stub_handler):
    for i in range(6):
        make_job(100 + i)
    ticks = iter(range(0, 1000, 8))  # each clock read is 8 s later than the last

    run = sweep.run_sweep(now=NOW, max_seconds=20, clock=lambda: next(ticks))
    assert 0 < run.handled < 6 and run.more is True
    assert statuses().count("pending") == 6 - run.handled


def test_the_time_bound_also_applies_before_the_first_job(stub_handler):
    make_job()
    run = sweep.run_sweep(now=NOW, max_seconds=0)
    assert (run.handled, run.more) == (0, True) and statuses() == ["pending"]


def test_a_failing_job_is_counted_released_and_not_retried_in_the_same_run(stub_handler, monkeypatch):
    bad, good = make_job(500), make_job(100)
    real = jobs.fire_job

    def fire(job_id, now=None):
        if job_id == bad.id:
            raise TransientJobError()
        return real(job_id, now=now)

    monkeypatch.setattr(jobs, "fire_job", fire)
    run = sweep.run_sweep(now=NOW)
    assert (run.failed, run.skipped, run.more) == (1, 1, False)
    assert ScheduledJob.objects.get(pk=good.pk).status == JobStatus.SKIPPED


def test_a_job_claimed_by_another_worker_meanwhile_is_not_counted_or_sent_twice(stub_handler, monkeypatch):
    job = make_job()
    real = jobs._claim

    def lose_the_race(job_id, now):
        real(job_id, now)  # the queue's own call claims it first
        return real(job_id, now)  # our claim then updates zero rows

    monkeypatch.setattr(jobs, "_claim", lose_the_race)
    run = sweep.run_sweep(now=NOW)
    assert (run.fired, run.skipped, run.failed) == (0, 0, 0)
    assert ScheduledJob.objects.get(pk=job.pk).status == JobStatus.FIRED


def test_jobs_that_are_not_pending_are_left_alone(stub_handler):
    for status in ("fired", "skipped", "cancelled", "failed"):
        make_job(status=status)
    assert sweep.run_sweep(now=NOW).handled == 0


def test_it_logs_a_sweep_run_line(stub_handler, caplog):
    make_job()
    caplog.set_level(logging.INFO)
    sweep.run_sweep(now=NOW)
    (line,) = [r for r in caplog.records if r.getMessage().startswith("sweep_run ")]
    assert set(line.push) == {"fired", "skipped", "failed", "more", "duration_ms"} and line.push["skipped"] == 1


def test_extra_steps_share_one_budget_and_run_in_order(stub_handler, monkeypatch):
    seen = []
    monkeypatch.setattr(
        sweep, "STEPS", (lambda run: seen.append(("a", run.max_jobs)), lambda run: seen.append(("b", run.handled)))
    )
    sweep.run_sweep(now=NOW, max_jobs=9)
    assert seen == [("a", 9), ("b", 0)]


def test_the_endpoint_runs_the_sweep_and_reports_what_it_did(client, settings, stub_handler):
    settings.CRON_SECRET = "s" * 24
    make_job()
    r = client.post("/api/v1/notifications/internal/sweep/", HTTP_AUTHORIZATION=f"Bearer {'s' * 24}")
    assert r.status_code == 200 and r.json() == {"fired": 0, "skipped": 1, "failed": 0, "more": False}
