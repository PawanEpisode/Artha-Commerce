"""
The timer-end pipeline end to end (PRD 5.2, FR-N4/N17/N18/N21): a student's timer actions plan, replace and cancel jobs
through the event bus, and firing a job judges the live timer before anything is sent. No network: `NullQueue` records
queue calls and `FakeChannel` records pushes.
"""

import json
import logging
import uuid
from datetime import timedelta

import pytest

from modules.focus.models import ActiveTimer
from modules.notifications import handlers, subscribers
from modules.notifications.domain.enums import JobStatus
from modules.notifications.models import Delivery, Notification, ScheduledJob
from modules.notifications.scheduling import jobs
from modules.notifications.tests.helpers import register
from modules.notifications.tests.timer_bench import FOCUS_END, NOW, USER

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def device():
    return register(USER, platform="android", browser="chrome").device


def all_jobs():
    return list(ScheduledJob.objects.order_by("created_at", "expected_version"))


def pending():
    return list(ScheduledJob.objects.filter(status=JobStatus.PENDING))


def job_for(timer, **extra):
    return ScheduledJob.objects.get(subject_key=str(timer.client_id), expected_version=timer.version, **extra)


def pushed(fake_push):
    """(title, body) of every push the fake channel received."""
    out = []
    for _, message in fake_push.sent:
        payload = json.loads(message.body)
        out.append((payload["title"], payload["body"]))
    return out


# --- planning ------------------------------------------------------------------------------------------------------


def test_starting_a_round_plans_exactly_one_job_at_its_end_and_publishes_it(bench, fake_queue):
    t = bench.start()
    (job,) = all_jobs()
    assert (job.user_id, job.kind, job.subject_key, job.expected_version) == (USER, "timer_end", str(t.client_id), 1)
    assert job.fire_at == FOCUS_END and job.status == JobStatus.PENDING
    assert job.external_id == f"null-{job.id}" and fake_queue.published == [(job.id, FOCUS_END)]
    assert job.context == {
        "phase": "focus",
        "round_number": 1,
        "minutes": 25,
        "subject_name": None,
        "break_minutes": 5,
        "next_round": None,
        "overtime": False,
    }


def test_the_job_carries_the_subject_name(bench, scheme):
    from modules.syllabus.models import Subject

    subject = Subject.objects.get(key="taxation")
    bench.start(subject_id=subject.id)
    assert all_jobs()[0].context["subject_name"] == subject.name


def test_a_retried_start_and_a_heartbeat_plan_nothing_new(bench, fake_queue):
    from modules.focus import services

    t = bench.start()
    bench.advance(seconds=30)
    bench.heartbeat()
    bench._do(services.start, client_id=t.client_id)  # the same start sent again
    assert len(all_jobs()) == 1 and len(fake_queue.published) == 1


def test_replaying_the_announcement_leaves_one_job_and_one_publish(bench, fake_queue):
    t = bench.start()
    payload = {
        "user_id": str(USER),
        "active": True,
        "client_id": str(t.client_id),
        "version": t.version,
        "phase": "focus",
        "ends_at": FOCUS_END,
        "paused": False,
        "at": NOW,
        "minutes": 25,
        "round": 1,
    }
    subscribers.on_timer_changed(**payload)
    subscribers.on_timer_changed(**payload)
    assert len(all_jobs()) == 1 and len(fake_queue.published) == 1


def test_a_new_version_supersedes_the_old_job_and_cancels_its_queue_message(bench, fake_queue):
    t = bench.start()
    first = job_for(t)
    bench.advance(minutes=10)
    extended = bench.extend()
    second = job_for(extended)
    first.refresh_from_db()
    assert first.status == JobStatus.CANCELLED and fake_queue.cancelled == [first.external_id]
    assert second.status == JobStatus.PENDING and second.fire_at == FOCUS_END + timedelta(minutes=5)
    assert pending() == [second] and fake_queue.published[-1] == (second.id, second.fire_at)


def test_exactly_one_pending_job_per_version_across_a_whole_session(bench):
    t = bench.start()
    bench.advance(minutes=5)
    bench.pause()
    assert pending() == []  # paused: no end is coming
    bench.advance(minutes=2)
    bench.resume()
    (resumed,) = pending()
    assert resumed.fire_at == FOCUS_END + timedelta(minutes=2)  # the pause pushed the end back by its length
    bench.extend()
    bench.change_context(version=bench.timer.version, changes={"activity_type": "practice"})
    (live,) = pending()
    assert (live.subject_key, live.expected_version) == (str(t.client_id), bench.timer.version)
    assert sorted(j.expected_version for j in all_jobs()) == [1, 3, 4, 5]  # version 2 was the pause: no job
    assert [j.status for j in all_jobs()].count(JobStatus.CANCELLED) == 3


@pytest.mark.parametrize("how", ["discard", "save_early"])
def test_stopping_the_round_cancels_what_was_waiting(bench, fake_queue, how):
    bench.start()
    bench.advance(minutes=5)
    bench.end(save=(how == "save_early"))
    assert pending() == [] and all_jobs()[0].status == JobStatus.CANCELLED
    assert len(fake_queue.cancelled) == 1


def test_a_break_that_begins_is_planned_as_break_over(bench, fake_push):
    t = bench.start()
    bench.set(FOCUS_END)
    bench.complete()  # the student's own screen reached zero: the break starts by itself
    (planned,) = pending()
    assert planned.context["phase"] == "short_break" and planned.context["next_round"] == 2
    assert planned.fire_at == FOCUS_END + timedelta(minutes=5) and planned.subject_key != str(t.client_id)
    jobs.fire_job(planned.id, now=planned.fire_at)
    assert pushed(fake_push) == [("Break over", "Ready for round 2?")]
    assert Notification.objects.get().event == "break_over"


def test_the_last_round_names_the_long_break_and_the_long_break_points_back_to_round_one(bench):
    from modules.focus import services

    services.update_settings(
        USER,
        {
            "preset": "custom",
            "focus_minutes": 5,
            "short_break_minutes": 1,
            "long_break_minutes": 7,
            "rounds_before_long": 2,
        },
    )
    bench.start()
    assert all_jobs()[-1].context["break_minutes"] == 1  # round 1 of 2: a short break follows
    bench.set(bench.timer.started_at + timedelta(minutes=5))
    bench.complete()  # the short break begins
    (short,) = pending()
    assert (short.context["phase"], short.context["next_round"]) == ("short_break", 2)
    bench.skip_break()
    bench.start()  # round 2 of 2
    (last,) = pending()
    assert (last.context["phase"], last.context["round_number"], last.context["break_minutes"]) == ("focus", 2, 7)
    bench.set(bench.timer.started_at + timedelta(minutes=5))
    bench.complete()  # the long break begins
    (long_break,) = pending()
    assert (long_break.context["phase"], long_break.context["next_round"]) == ("long_break", 1)


# --- firing and judging --------------------------------------------------------------------------------------------


def test_an_unchanged_round_sends_one_push_at_the_end(bench, fake_push, caplog):
    t = bench.start()
    job = job_for(t)
    caplog.set_level(logging.INFO)
    result = jobs.fire_job(job.id, now=FOCUS_END + timedelta(seconds=1))
    assert (result.outcome, result.delivery) == (jobs.FireOutcome.NOTIFIED, "sent")
    assert pushed(fake_push) == [("Round 1 done", "25 minutes. Take 5, you earned it.")]
    n = Notification.objects.get()
    assert n.dedupe_key == f"timer_end:{t.client_id}:1" and n.tag == f"timer:{t.client_id}" and n.priority == 0
    (delivery,) = Delivery.objects.all()
    assert delivery.status == "sent" and delivery.lateness_ms == 1000 and delivery.counts_toward_cap is False
    job.refresh_from_db()
    assert job.status == JobStatus.FIRED and job.fired_at == FOCUS_END + timedelta(seconds=1) and job.attempts == 1
    (line,) = [r for r in caplog.records if r.getMessage().startswith("job_fired ")]
    assert line.push == {"kind": "timer_end", "event": "timer_end", "overdue_ms": 1000}


def test_the_alert_names_the_subject(bench, fake_push, scheme):
    from modules.syllabus.models import Subject

    subject = Subject.objects.get(key="taxation")
    t = bench.start(subject_id=subject.id)
    jobs.fire_job(job_for(t).id, now=FOCUS_END)
    assert pushed(fake_push) == [("Round 1 done", f"25 minutes on {subject.name}. Take 5, you earned it.")]


def test_with_overtime_the_alert_says_the_target_is_reached_and_the_round_runs_on(bench, fake_push):
    t = bench.start(overtime=True)
    bench.set(FOCUS_END - timedelta(seconds=30))
    bench.heartbeat()  # the student is around, so the round keeps running past zero
    jobs.fire_job(job_for(t).id, now=FOCUS_END)
    assert pushed(fake_push) == [
        ("Round target reached", "25 minutes. The timer is still running; stop when you are ready.")
    ]
    assert bench.timer is not None and bench.timer.version == t.version  # firing never touched the timer


def test_a_change_made_while_overtime_runs_does_not_alert_again_for_the_same_end(bench, fake_push):
    t = bench.start(overtime=True)
    jobs.fire_job(job_for(t).id, now=FOCUS_END)
    bench.set(FOCUS_END + timedelta(minutes=3))
    bench.heartbeat()
    bench.change_context(version=bench.timer.version, changes={"activity_type": "practice"})
    assert pending() == []  # the target moment is behind us: nothing to plan
    assert len(fake_push.sent) == 1


def test_paused_one_second_before_the_end_sends_nothing(bench, fake_push):
    t = bench.start()
    job = job_for(t)
    bench.set(FOCUS_END - timedelta(seconds=1))
    bench.pause()
    assert jobs.fire_job(job.id, now=FOCUS_END).outcome is jobs.FireOutcome.IGNORED  # it was cancelled with the pause
    assert fake_push.sent == [] and not Notification.objects.exists()


def test_the_judge_alone_also_stops_a_job_whose_cancel_never_happened(bench, fake_push):
    """Safety net: even if the subscriber missed a change, the job notices at fire time."""
    t = bench.start()
    job = job_for(t)
    bench.set(FOCUS_END - timedelta(seconds=1))
    bench.pause()
    ScheduledJob.objects.filter(pk=job.pk).update(status=JobStatus.PENDING)  # as if the cancel had been lost
    result = jobs.fire_job(job.id, now=FOCUS_END)
    assert (result.outcome, result.reason) == (jobs.FireOutcome.SKIPPED, "changed")
    job.refresh_from_db()
    assert job.status == JobStatus.SKIPPED and job.skip_reason == "changed" and fake_push.sent == []


def test_plus_five_minutes_moves_the_alert_and_the_old_job_is_skipped_changed(bench, fake_push):
    t = bench.start()
    old = job_for(t)
    bench.advance(minutes=20)
    new = job_for(bench.extend())
    ScheduledJob.objects.filter(pk=old.pk).update(status=JobStatus.PENDING)  # the old message still reaches us
    assert jobs.fire_job(old.id, now=FOCUS_END).reason == "changed"
    assert fake_push.sent == []  # nothing at the old end
    assert new.fire_at == FOCUS_END + timedelta(minutes=5)
    assert jobs.fire_job(new.id, now=new.fire_at).delivery == "sent"
    assert pushed(fake_push) == [("Round 1 done", "30 minutes. Take 5, you earned it.")]


def test_a_discarded_round_is_gone(bench, fake_push):
    t = bench.start()
    job = job_for(t)
    bench.advance(minutes=3)
    bench.end(save=False)
    ScheduledJob.objects.filter(pk=job.pk).update(status=JobStatus.PENDING)
    result = jobs.fire_job(job.id, now=FOCUS_END)
    assert (result.outcome, result.reason) == (jobs.FireOutcome.SKIPPED, "gone")
    assert fake_push.sent == []


def test_a_new_phase_with_another_client_id_is_changed_not_gone(bench, fake_push):
    t = bench.start()
    job = job_for(t)
    bench.set(FOCUS_END)
    bench.complete()  # the break begins under a new client id
    ScheduledJob.objects.filter(pk=job.pk).update(status=JobStatus.PENDING)
    assert jobs.fire_job(job.id, now=FOCUS_END).reason == "changed"


def test_a_job_fired_more_than_five_minutes_late_is_dropped_as_stale(bench, fake_push):
    t = bench.start()
    job = job_for(t)
    result = jobs.fire_job(job.id, now=FOCUS_END + timedelta(minutes=6))
    assert (result.outcome, result.reason, result.delivery) == (jobs.FireOutcome.SKIPPED, "stale", "suppressed")
    assert fake_push.sent == []
    job.refresh_from_db()
    assert (job.status, job.skip_reason) == (JobStatus.SKIPPED, "stale")
    (row,) = Delivery.objects.all()
    assert (row.status, row.suppress_reason) == ("suppressed", "stale")  # FR-N21: recorded, not silently lost


def test_four_minutes_fifty_nine_late_is_still_sent(bench, fake_push):
    t = bench.start()
    result = jobs.fire_job(job_for(t).id, now=FOCUS_END + timedelta(minutes=4, seconds=59))
    assert result.delivery == "sent" and len(fake_push.sent) == 1


def test_when_the_student_was_away_the_push_still_goes_out_even_after_a_request_settled_the_round(bench, fake_push):
    t = bench.start()  # no heartbeat: the tab was hidden
    job = job_for(t)
    bench.set(FOCUS_END + timedelta(seconds=1))
    bench.sync()  # another request reads the timer first: the lazy settle marks the round away_pending (version + 1)
    assert bench.timer.away_pending and bench.timer.version == t.version + 1
    assert pending() == [job]  # an away marker is not a student action: the job for that end stays
    result = jobs.fire_job(job.id, now=FOCUS_END + timedelta(seconds=2))
    assert result.delivery == "sent"
    assert pushed(fake_push) == [("Round 1 done", "25 minutes. Take 5, you earned it.")]  # it ended: no "still running"


def test_a_job_called_before_the_end_is_retried_not_sent(bench, fake_push):
    t = bench.start()
    job = job_for(t)
    from modules.notifications.errors import TransientJobError

    with pytest.raises(TransientJobError):
        jobs.fire_job(job.id, now=FOCUS_END - timedelta(minutes=1))
    job.refresh_from_db()
    assert job.status == JobStatus.PENDING and job.fired_at is None and job.attempts == 1 and fake_push.sent == []


def test_firing_never_changes_the_timer_row(bench):
    t = bench.start(overtime=True)
    job = job_for(t)
    before = ActiveTimer.objects.filter(pk=USER).values().get()
    jobs.fire_job(job.id, now=FOCUS_END)
    assert ActiveTimer.objects.filter(pk=USER).values().get() == before


# --- the atomic claim ----------------------------------------------------------------------------------------------


def test_two_fires_of_one_job_make_one_delivery(bench, fake_push):
    t = bench.start()
    job = job_for(t)
    first = jobs.fire_job(job.id, now=FOCUS_END)
    again = jobs.fire_job(job.id, now=FOCUS_END + timedelta(seconds=1))
    assert (first.outcome, again.outcome, again.reason) == (
        jobs.FireOutcome.NOTIFIED,
        jobs.FireOutcome.IGNORED,
        "not_pending",
    )
    assert len(fake_push.sent) == 1 and Notification.objects.count() == 1 and Delivery.objects.count() == 1


def test_a_second_worker_arriving_while_the_first_is_mid_flight_does_nothing(bench, fake_push, monkeypatch):
    """The race itself: a retry hits the endpoint between the first call's claim and its send."""
    t = bench.start()
    job = job_for(t)
    inner = []
    real = handlers.TimerEndHandler.judge

    def judge_while_a_second_call_arrives(self, j, now):
        inner.append(jobs.fire_job(job.id, now=now))
        return real(self, j, now)

    monkeypatch.setattr(handlers.TimerEndHandler, "judge", judge_while_a_second_call_arrives)
    outer = jobs.fire_job(job.id, now=FOCUS_END)
    assert [r.outcome for r in inner] == [jobs.FireOutcome.IGNORED] and outer.outcome is jobs.FireOutcome.NOTIFIED
    assert len(fake_push.sent) == 1


def test_a_missing_job_is_ignored_for_example_after_account_erasure(bench, fake_push):
    t = bench.start()
    job = job_for(t)
    from modules.notifications.services.erasure import delete_all_for_user

    delete_all_for_user(USER)
    result = jobs.fire_job(job.id, now=FOCUS_END)
    assert (result.outcome, result.reason) == (jobs.FireOutcome.IGNORED, "gone") and fake_push.sent == []
    assert jobs.fire_job(uuid.uuid4()).reason == "gone"


# --- failures ------------------------------------------------------------------------------------------------------


def test_a_failing_send_releases_the_job_for_a_retry_and_fails_it_after_three_attempts(bench, fake_push, monkeypatch):
    from modules.notifications.errors import TransientJobError
    from modules.notifications.services import notify as notify_service

    t = bench.start()
    job = job_for(t)

    def boom(*a, **k):
        raise RuntimeError("database went away")

    monkeypatch.setattr(notify_service, "notify", boom)
    for attempt in (1, 2):
        with pytest.raises(TransientJobError):
            jobs.fire_job(job.id, now=FOCUS_END)
        job.refresh_from_db()
        assert (job.status, job.attempts, job.fired_at) == (JobStatus.PENDING, attempt, None)
    with pytest.raises(TransientJobError):
        jobs.fire_job(job.id, now=FOCUS_END)
    job.refresh_from_db()
    assert (job.status, job.attempts) == (JobStatus.FAILED, 3)
    assert jobs.fire_job(job.id).outcome is jobs.FireOutcome.IGNORED


def test_a_job_of_an_unknown_kind_is_failed_not_retried(bench):
    t = bench.start()
    job = job_for(t)
    handlers._registry.pop("timer_end")
    result = jobs.fire_job(job.id, now=FOCUS_END)
    job.refresh_from_db()
    assert (result.outcome, result.reason, job.status) == (jobs.FireOutcome.SKIPPED, "unknown_kind", JobStatus.FAILED)


def test_a_queue_outage_never_fails_the_students_request_and_the_job_waits_for_the_sweep(bench, fake_queue, caplog):
    fake_queue.fail_with = RuntimeError("qstash is down")
    caplog.set_level(logging.WARNING)
    t = bench.start()  # does not raise
    (job,) = all_jobs()
    assert job.status == JobStatus.PENDING and job.external_id is None and job.fire_at == FOCUS_END
    assert [r.push["error_type"] for r in caplog.records if r.getMessage().startswith("job_publish_failed")] == [
        "RuntimeError"
    ]
    bench.advance(minutes=1)
    bench.extend()  # cancelling the old message fails too, still no error for the student
    assert [j.status for j in all_jobs()] == [JobStatus.CANCELLED, JobStatus.PENDING]
    assert t.client_id


# --- kill switches (FR-N15, FR-N32) --------------------------------------------------------------------------------


def test_with_the_environment_switch_off_a_waiting_job_is_skipped_disabled(bench, fake_push, settings):
    job = job_for(bench.start())
    settings.NOTIFICATIONS_ENABLED = False
    result = jobs.fire_job(job.id, now=FOCUS_END)
    job.refresh_from_db()
    assert (result.outcome, result.reason) == (jobs.FireOutcome.SKIPPED, "disabled")
    assert (job.status, job.skip_reason) == (JobStatus.SKIPPED, "disabled") and fake_push.sent == []
    assert not Notification.objects.exists()


def test_with_the_environment_switch_off_nothing_is_planned_or_cancelled(bench, fake_queue, settings):
    settings.NOTIFICATIONS_ENABLED = False
    bench.start()
    assert all_jobs() == [] and fake_queue.published == []


def test_with_the_posthog_flag_off_a_waiting_job_is_skipped_flag_off(bench, fake_push, monkeypatch):
    job = job_for(bench.start())
    monkeypatch.setattr("modules.notifications.flags.flag_enabled", lambda *a, **k: False)
    result = jobs.fire_job(job.id, now=FOCUS_END)
    job.refresh_from_db()
    assert (result.outcome, result.reason) == (jobs.FireOutcome.SKIPPED, "flag_off")
    assert (job.status, job.skip_reason) == (JobStatus.SKIPPED, "flag_off") and fake_push.sent == []


def test_with_the_posthog_flag_off_nothing_is_planned(bench, fake_queue, monkeypatch):
    monkeypatch.setattr("modules.notifications.flags.flag_enabled", lambda *a, **k: False)
    bench.start()
    assert all_jobs() == [] and fake_queue.published == []


def test_the_sending_flag_is_strict_so_an_unreachable_flag_service_means_no_job(bench, fake_queue, monkeypatch):
    """PostHog down: `flag_enabled(strict=True)` answers False, so nothing is scheduled (FR-N14)."""
    seen = []
    monkeypatch.setattr(
        "modules.notifications.flags.flag_enabled", lambda name, user, strict=False: seen.append(strict) or not strict
    )
    bench.start()
    assert seen and all(seen) and all_jobs() == []


def test_a_disabled_event_is_skipped_when_its_job_fires(bench, fake_push, settings):
    job = job_for(bench.start())
    settings.NOTIFICATIONS_DISABLED_EVENTS = frozenset({"timer_end"})
    result = jobs.fire_job(job.id, now=FOCUS_END)
    assert (result.outcome, result.reason) == (jobs.FireOutcome.SKIPPED, "disabled") and fake_push.sent == []


def test_a_disabled_event_is_not_planned(bench, fake_queue, settings):
    settings.NOTIFICATIONS_DISABLED_EVENTS = frozenset({"timer_end"})
    bench.start()
    assert all_jobs() == [] and fake_queue.published == []


def test_disabling_timer_end_leaves_break_over_alive(bench, settings):
    settings.NOTIFICATIONS_DISABLED_EVENTS = frozenset({"timer_end"})
    bench.start()
    assert all_jobs() == []
    bench.set(FOCUS_END)
    bench.complete()
    (job,) = all_jobs()
    assert job.context["phase"] == "short_break"


def test_a_student_who_switched_timer_alerts_off_gets_a_suppressed_row_not_a_push(bench, fake_push):
    from modules.notifications.models import Preference

    Preference.objects.create(user_id=USER, category="timer", channel="push", enabled=False)
    t = bench.start()
    result = jobs.fire_job(job_for(t).id, now=FOCUS_END)
    assert (result.outcome, result.delivery) == (jobs.FireOutcome.NOTIFIED, "suppressed")
    assert fake_push.sent == [] and Delivery.objects.get().suppress_reason == "preference"
