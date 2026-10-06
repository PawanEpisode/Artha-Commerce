"""
The tracker alerts that start from an event (X-01.1 W3.2): the long stopwatch and the daily goal. A student's real
`tracking` actions announce, the listeners plan or cancel jobs, and firing a job judges the facts before anything is sent.
No network: `NullQueue` records queue calls and `FakeChannel` records pushes.
"""

import json
import logging
from datetime import UTC, datetime, timedelta

import pytest

from modules.notifications import subscribers
from modules.notifications.domain.enums import JobKind, JobStatus
from modules.notifications.errors import TransientJobError
from modules.notifications.models import Delivery, Notification, NotificationSettings, Preference, ScheduledJob
from modules.notifications.scheduling import jobs
from modules.notifications.tests.helpers import register
from modules.notifications.tests.tracker_bench import NOW, OTHER, THREE_HOURS, USER
from modules.tracking import services
from modules.tracking.models import ActiveStopwatch

pytestmark = pytest.mark.django_db
MARK = NOW + THREE_HOURS  # 07:30 UTC, 13:00 in India


@pytest.fixture(autouse=True)
def device():
    return register(USER, platform="android", browser="chrome").device


def long_jobs(user=USER):
    return list(ScheduledJob.objects.filter(user_id=user, kind=JobKind.STOPWATCH_LONG).order_by("expected_version"))


def goal_jobs(user=USER):
    return list(ScheduledJob.objects.filter(user_id=user, kind=JobKind.DELIVER_DEFERRED).order_by("created_at"))


def pending(user=USER):
    return list(ScheduledJob.objects.filter(user_id=user, status=JobStatus.PENDING))


def pushed(fake_push):
    out = []
    for _, message in fake_push.sent:
        payload = json.loads(message.body)
        out.append((payload["title"], payload["body"], payload["url"].split("?")[0]))
    return out


# --- the long stopwatch: planning ----------------------------------------------------------------------------------


def test_starting_a_stopwatch_plans_one_job_three_hours_ahead_and_publishes_it(tracker, fake_queue):
    sw = tracker.start()
    (job,) = long_jobs()
    assert (job.user_id, job.subject_key, job.expected_version) == (USER, str(sw.client_id), sw.version)
    assert job.fire_at == MARK and job.status == JobStatus.PENDING and job.context == {}
    assert job.external_id == f"null-{job.id}" and fake_queue.published == [(job.id, MARK)]


def test_a_pause_cancels_it_and_a_resume_plans_it_again_pushed_back_by_the_pause(tracker, fake_queue):
    tracker.start()
    first = long_jobs()[0]
    tracker.advance(hours=1)
    tracker.pause()
    first.refresh_from_db()
    assert first.status == JobStatus.CANCELLED and pending() == [] and fake_queue.cancelled == [first.external_id]
    tracker.advance(minutes=20)
    tracker.resume()
    (live,) = pending()
    assert live.fire_at == MARK + timedelta(minutes=20)  # three counted hours: the pause does not count
    assert [j.status for j in long_jobs()] == [JobStatus.CANCELLED, JobStatus.PENDING]


def test_changing_the_subject_replaces_the_job_with_one_for_the_new_version(tracker):
    tracker.start()
    old = long_jobs()[0]
    tracker.advance(minutes=30)
    tracker.retag(activity_type="practice")
    old.refresh_from_db()
    (live,) = pending()
    assert old.status == JobStatus.CANCELLED and live.expected_version == tracker.stopwatch.version
    assert live.fire_at == MARK  # the mark did not move


def test_stopping_or_discarding_cancels_what_was_waiting(tracker, fake_queue):
    tracker.start()
    tracker.advance(minutes=30)
    tracker.stop(save=False)
    assert pending() == [] and long_jobs()[0].status == JobStatus.CANCELLED and len(fake_queue.cancelled) == 1


def test_a_retried_start_and_a_heartbeat_plan_nothing_new(tracker, fake_queue):
    sw = tracker.start()
    tracker.advance(minutes=1)
    tracker.sync(alive=True)
    tracker._do(services.start_stopwatch, client_id=sw.client_id)  # the same start sent again
    assert len(long_jobs()) == 1 and len(fake_queue.published) == 1


def test_replaying_the_announcement_leaves_one_job_and_one_publish(tracker, fake_queue):
    sw = tracker.start()
    payload = {
        "user_id": str(USER),
        "active": True,
        "client_id": str(sw.client_id),
        "version": sw.version,
        "started_at": sw.started_at,
        "paused": False,
        "paused_total_seconds": 0,
        "at": NOW,
    }
    subscribers.on_stopwatch_changed(**payload)
    subscribers.on_stopwatch_changed(**payload)
    assert len(long_jobs()) == 1 and len(fake_queue.published) == 1


def test_a_stopwatch_resumed_after_the_mark_plans_nothing_because_the_alert_was_due_earlier(tracker):
    tracker.start()
    tracker.advance(hours=3, minutes=5)
    tracker.pause()
    tracker.advance(minutes=10)
    tracker.resume()
    assert pending() == []


def test_erasing_the_account_cancels_the_job(tracker):
    tracker.start()
    tracker.erase()
    assert pending() == []


def test_nothing_is_planned_while_the_feature_is_off(tracker, settings):
    settings.NOTIFICATIONS_ENABLED = False
    tracker.start()
    assert long_jobs() == []


def test_nothing_is_planned_when_the_event_is_switched_off(tracker, settings):
    settings.NOTIFICATIONS_DISABLED_EVENTS = ["stopwatch_long"]
    tracker.start()
    assert long_jobs() == []


def test_nothing_is_planned_when_the_sending_flag_is_off(tracker, monkeypatch):
    monkeypatch.setattr("modules.notifications.flags.flag_enabled", lambda *a, **k: False)
    tracker.start()
    assert long_jobs() == []


# --- the long stopwatch: firing ------------------------------------------------------------------------------------


def test_it_sends_one_alert_when_the_stopwatch_has_run_three_hours(tracker, fake_push):
    tracker.start()
    (job,) = long_jobs()
    result = jobs.fire_job(job.id, now=MARK)
    assert (result.outcome, result.delivery) == (jobs.FireOutcome.NOTIFIED, "sent")
    assert pushed(fake_push) == [
        ("Stopwatch still running", "3 h so far. Pause or stop it if you are done.", "/app/tracker")
    ]
    n = Notification.objects.get()
    assert (n.event, n.category, n.priority, n.dedupe_key) == (
        "stopwatch_long",
        "tracker",
        1,
        f"stopwatch_long:{tracker.stopwatch.client_id}",
    )
    assert n.expires_at == MARK + timedelta(hours=1)


def test_the_alert_counts_the_time_the_stopwatch_really_ran_when_the_job_is_a_little_late(tracker, fake_push):
    tracker.start()
    jobs.fire_job(long_jobs()[0].id, now=MARK + timedelta(minutes=12))
    assert pushed(fake_push)[0][1] == "3 h 12 min so far. Pause or stop it if you are done."


def test_a_stopwatch_paused_a_second_before_the_mark_sends_nothing(tracker, fake_push):
    tracker.start()
    job = long_jobs()[0]
    tracker.set(MARK - timedelta(seconds=1))
    tracker.pause()
    assert jobs.fire_job(job.id, now=MARK).outcome is jobs.FireOutcome.IGNORED  # cancelled with the pause
    assert fake_push.sent == [] and not Notification.objects.exists()


def test_the_judge_alone_also_stops_a_job_whose_cancel_never_happened(tracker, fake_push):
    tracker.start()
    job = long_jobs()[0]
    tracker.advance(hours=1)
    tracker.pause()
    ScheduledJob.objects.filter(pk=job.pk).update(status=JobStatus.PENDING)  # as if the cancel had been lost
    result = jobs.fire_job(job.id, now=MARK)
    assert (result.outcome, result.reason) == (jobs.FireOutcome.SKIPPED, "changed")  # the pause bumped the version
    assert fake_push.sent == []


def test_a_job_for_a_stopwatch_that_is_gone_is_skipped_gone(tracker, fake_push):
    tracker.start()
    job = long_jobs()[0]
    tracker.advance(minutes=20)
    tracker.stop(save=False)
    ScheduledJob.objects.filter(pk=job.pk).update(status=JobStatus.PENDING)
    assert jobs.fire_job(job.id, now=MARK).reason == "gone" and fake_push.sent == []


def test_an_idle_prompt_left_unanswered_pauses_it_so_no_alert_goes(tracker, fake_push):
    tracker.start()
    job = long_jobs()[0]
    tracker.advance(hours=2)
    tracker._do(services.answer_idle, answer="prompted")
    ScheduledJob.objects.filter(pk=job.pk).update(status=JobStatus.PENDING)
    result = jobs.fire_job(job.id, now=MARK)  # an hour after the prompt: the lazy settle would have paused it
    assert result.reason == "paused" and fake_push.sent == []


def test_a_job_called_before_the_mark_is_retried_not_sent(tracker, fake_push):
    tracker.start()
    job = long_jobs()[0]
    with pytest.raises(TransientJobError):
        jobs.fire_job(job.id, now=MARK - timedelta(minutes=1))
    job.refresh_from_db()
    assert job.status == JobStatus.PENDING and job.attempts == 1 and fake_push.sent == []


def test_firing_never_changes_the_stopwatch_row(tracker):
    tracker.start()
    before = ActiveStopwatch.objects.filter(pk=USER).values().get()
    jobs.fire_job(long_jobs()[0].id, now=MARK)
    assert ActiveStopwatch.objects.filter(pk=USER).values().get() == before


def test_two_fires_of_one_job_make_one_alert(tracker, fake_push):
    tracker.start()
    job = long_jobs()[0]
    first = jobs.fire_job(job.id, now=MARK)
    again = jobs.fire_job(job.id, now=MARK + timedelta(seconds=1))
    assert first.delivery == "sent" and again.outcome is jobs.FireOutcome.IGNORED
    assert len(fake_push.sent) == 1 and Notification.objects.count() == 1


def test_once_per_session_even_when_the_job_is_planned_again(tracker, fake_push):
    sw = tracker.start()
    first = long_jobs()[0]
    jobs.fire_job(first.id, now=MARK)
    # A later version of the same session (a retag after the mark) can never ask the student twice.
    again = ScheduledJob.objects.create(
        user_id=USER,
        kind=JobKind.STOPWATCH_LONG,
        subject_key=str(sw.client_id),
        expected_version=sw.version + 5,
        fire_at=MARK,
    )
    ActiveStopwatch.objects.filter(pk=USER).update(version=sw.version + 5)
    result = jobs.fire_job(again.id, now=MARK + timedelta(minutes=1))
    assert result.delivery == "already_sent" and len(fake_push.sent) == 1 and Notification.objects.count() == 1


def test_a_new_stopwatch_the_next_day_is_a_new_session_with_its_own_alert(tracker, fake_push):
    tracker.start()
    jobs.fire_job(long_jobs()[0].id, now=MARK)
    tracker.stop(save=False)
    tracker.advance(days=1)
    tracker.start()
    (tomorrows,) = pending()
    jobs.fire_job(tomorrows.id, now=tracker.now + THREE_HOURS)
    assert len(fake_push.sent) == 2 and Notification.objects.count() == 2


def test_the_event_kill_switch_stops_a_job_that_was_already_planned(tracker, fake_push, settings):
    tracker.start()
    settings.NOTIFICATIONS_DISABLED_EVENTS = ["stopwatch_long"]
    result = jobs.fire_job(long_jobs()[0].id, now=MARK)
    assert (result.outcome, result.reason) == (jobs.FireOutcome.SKIPPED, "disabled") and fake_push.sent == []


def test_the_sending_flag_stops_a_job_that_was_already_planned(tracker, fake_push, monkeypatch):
    tracker.start()
    monkeypatch.setattr("modules.notifications.flags.flag_enabled", lambda *a, **k: False)
    assert jobs.fire_job(long_jobs()[0].id, now=MARK).reason == "flag_off" and fake_push.sent == []


def test_switching_the_tracker_category_off_suppresses_the_push_but_keeps_the_record(tracker, fake_push):
    Preference.objects.create(user_id=USER, category="tracker", channel="push", enabled=False)
    tracker.start()
    result = jobs.fire_job(long_jobs()[0].id, now=MARK)
    assert result.delivery == "suppressed" and fake_push.sent == []
    assert Delivery.objects.get().suppress_reason == "preference"


def test_a_stopwatch_alert_inside_quiet_hours_never_arrives_because_it_expires_in_an_hour(tracker, fake_push):
    tracker.set(
        datetime(2026, 10, 5, 15, 30, tzinfo=UTC)
    )  # 21:00 in India: the alert falls at 00:00, deep in quiet hours
    tracker.start()
    (job,) = long_jobs()
    result = jobs.fire_job(job.id, now=job.fire_at)
    assert result.delivery == "suppressed" and fake_push.sent == []
    assert (
        Delivery.objects.get().suppress_reason == "quiet_hours"
        and ScheduledJob.objects.filter(kind=JobKind.DELIVER_DEFERRED).count() == 0
    )


# --- the daily goal ------------------------------------------------------------------------------------------------


def test_reaching_the_goal_creates_the_alert_and_a_job_to_send_it_outside_the_request(tracker, fake_push, fake_queue):
    tracker.study(130)
    n = Notification.objects.get()
    assert (n.event, n.dedupe_key, n.deep_link) == ("goal_reached", "goal:2026-10-05", "/app/tracker")
    assert n.expires_at == NOW + timedelta(hours=6)
    assert fake_push.sent == []  # nothing is pushed inside the request that recorded the time
    (job,) = goal_jobs()
    assert job.context == {"event": "goal_reached"} and job.fire_at == NOW + timedelta(seconds=2)
    assert fake_queue.published == [(job.id, job.fire_at)]


def test_the_job_sends_the_alert_with_the_time_studied(tracker, fake_push):
    tracker.study(192)
    result = jobs.fire_job(goal_jobs()[0].id, now=NOW + timedelta(seconds=2))
    assert result.delivery == "sent"
    assert pushed(fake_push) == [("Daily goal reached", "3 h 12 min studied today.", "/app/tracker")]


def test_below_the_goal_nothing_is_created(tracker):
    tracker.study(119)
    assert not Notification.objects.exists() and goal_jobs() == []


def test_the_goal_alert_comes_once_a_day(tracker, fake_push):
    first, _ = tracker.study(130)
    tracker.study(60, ended_ago=timedelta(hours=3))
    tracker._do(services.delete_session, first.id)
    tracker.study(130, ended_ago=timedelta(hours=6))  # the goal is reached a second time the same day
    assert Notification.objects.filter(event="goal_reached").count() == 1 and len(goal_jobs()) == 1
    jobs.fire_job(goal_jobs()[0].id, now=NOW + timedelta(seconds=2))
    assert len(fake_push.sent) == 1


def test_the_next_day_brings_its_own_alert(tracker, fake_push):
    tracker.study(130)
    tracker.advance(days=1)
    tracker.study(130)
    keys = sorted(Notification.objects.values_list("dedupe_key", flat=True))
    assert keys == ["goal:2026-10-05", "goal:2026-10-06"] and len(goal_jobs()) == 2


def test_the_students_own_goal_and_time_zone_decide(tracker, fake_push):
    services.update_settings(USER, {"tz": "America/New_York"})
    services.set_goals(USER, [{"period": "daily", "target_minutes": 30, "subject_id": None}])
    tracker.study(45)
    n = Notification.objects.get()
    assert n.dedupe_key == "goal:2026-10-05" and n.context["goal_minutes"] == 30
    tracker.advance(hours=8)  # 12:30 UTC on 5 Oct is 08:30 in New York: still the same local day there
    assert Notification.objects.count() == 1


def test_a_goal_in_quiet_hours_is_held_and_arrives_when_they_end(tracker, fake_push):
    tracker.set(datetime(2026, 10, 5, 0, 30, tzinfo=UTC))  # 06:00 in India, quiet hours end at 07:00
    tracker.study(130)
    (job,) = goal_jobs()
    result = jobs.fire_job(job.id, now=job.fire_at)
    assert result.delivery == "deferred" and fake_push.sent == []
    held = goal_jobs()
    assert [j.status for j in held] == [JobStatus.FIRED, JobStatus.PENDING]
    assert held[1].fire_at == datetime(2026, 10, 5, 1, 30, tzinfo=UTC)
    assert jobs.fire_job(held[1].id, now=held[1].fire_at).delivery == "sent"
    assert pushed(fake_push) == [("Daily goal reached", "2 h 10 min studied today.", "/app/tracker")]


def test_a_goal_at_eleven_at_night_never_arrives_because_it_expires_before_the_morning(tracker, fake_push):
    tracker.set(
        datetime(2026, 10, 5, 17, 30, tzinfo=UTC)
    )  # 23:00 in India; the alert is worth six hours, quiet ends in eight
    tracker.study(130)
    (job,) = goal_jobs()
    result = jobs.fire_job(job.id, now=job.fire_at)
    assert result.delivery == "suppressed" and fake_push.sent == []
    assert len(goal_jobs()) == 1 and Delivery.objects.get().suppress_reason == "quiet_hours"
    assert Notification.objects.count() == 1  # still readable in the inbox until it expires


def test_the_goal_alert_obeys_the_daily_cap(tracker, fake_push):
    from modules.notifications.models import Device

    d = Device.objects.get(user_id=USER)
    for i in range(4):  # priority 1 may use one slot beyond the cap of three
        other = Notification.objects.create(
            user_id=USER,
            category="revision",
            event="revision_due",
            dedupe_key=f"revision:{i}",
            title="t",
            body="b",
            deep_link="/app/revision",
            priority=2,
        )
        Delivery.objects.create(
            notification=other,
            user_id=USER,
            device=d,
            channel="push",
            status="sent",
            counts_toward_cap=True,
            sent_at=NOW - timedelta(minutes=30),
            attempted_at=NOW - timedelta(minutes=30),
        )
    tracker.study(130)
    result = jobs.fire_job(goal_jobs()[0].id, now=NOW + timedelta(seconds=2))
    assert (
        result.delivery == "suppressed"
        and Delivery.objects.get(notification__event="goal_reached").suppress_reason == "cap"
    )


def test_nothing_is_created_while_the_feature_or_the_event_is_off(tracker, settings):
    settings.NOTIFICATIONS_DISABLED_EVENTS = ["goal_reached"]
    tracker.study(130)
    assert not Notification.objects.exists()
    settings.NOTIFICATIONS_DISABLED_EVENTS = []
    settings.NOTIFICATIONS_ENABLED = False
    tracker.study(60, ended_ago=timedelta(hours=4))
    assert not Notification.objects.exists()


def test_nothing_is_created_when_the_sending_flag_is_off(tracker, monkeypatch):
    monkeypatch.setattr("modules.notifications.flags.flag_enabled", lambda *a, **k: False)
    tracker.study(130)
    assert not Notification.objects.exists() and goal_jobs() == []


def test_the_kill_switch_stops_a_goal_job_that_was_already_planned(tracker, fake_push, settings):
    tracker.study(130)
    settings.NOTIFICATIONS_DISABLED_EVENTS = ["goal_reached"]
    result = jobs.fire_job(goal_jobs()[0].id, now=NOW + timedelta(seconds=2))
    assert result.reason == "disabled" and fake_push.sent == []
    assert not Delivery.objects.exists()  # it was never held, so there is no row to close; the alert stays in the inbox


def test_the_stopwatch_saving_a_session_that_reaches_the_goal_alerts_once(tracker, fake_push):
    services.set_goals(USER, [{"period": "daily", "target_minutes": 15, "subject_id": None}])
    tracker.start()
    tracker.advance(minutes=20)
    tracker.stop()
    assert Notification.objects.filter(event="goal_reached").count() == 1
    assert [j.kind for j in ScheduledJob.objects.filter(status=JobStatus.PENDING)] == [JobKind.DELIVER_DEFERRED]


# --- per student ---------------------------------------------------------------------------------------------------


def test_one_students_stopwatch_and_goal_never_alert_another(
    tracker, fake_push, monkeypatch, django_capture_on_commit_callbacks
):
    from modules.notifications.tests.tracker_bench import Tracker

    register(OTHER, platform="ios", browser="safari")
    theirs = Tracker(monkeypatch, django_capture_on_commit_callbacks, user=OTHER)
    theirs.start()
    theirs.study(10, ended_ago=timedelta(hours=1))  # a stopwatch and a little study: no goal
    mine = tracker
    mine.set(NOW)
    mine.study(130, ended_ago=timedelta(hours=1))
    assert [j.user_id for j in goal_jobs(OTHER)] == [] and len(goal_jobs(USER)) == 1
    assert len(long_jobs(OTHER)) == 1 and long_jobs(USER) == []
    for job in ScheduledJob.objects.all():
        jobs.fire_job(job.id, now=max(MARK, job.fire_at))
    owners = {n.user_id: n.event for n in Notification.objects.all()}
    assert owners == {USER: "goal_reached", OTHER: "stopwatch_long"}
    assert {d.user_id for d in Delivery.objects.filter(status="sent")} == {USER, OTHER} and len(fake_push.sent) == 2


def test_the_log_names_the_job_and_never_the_text(tracker, fake_push, caplog):
    caplog.set_level(logging.INFO)
    tracker.start()
    jobs.fire_job(long_jobs()[0].id, now=MARK)
    fired = [r for r in caplog.records if r.getMessage().startswith("job_fired ")]
    assert fired and fired[0].push["kind"] == "stopwatch_long" and fired[0].push["event"] == "stopwatch_long"
    assert "so far" not in caplog.text and "Stopwatch still running" not in caplog.text


def test_settings_row_is_not_needed_for_defaults(tracker):
    assert not NotificationSettings.objects.exists()
    tracker.start()
    assert len(long_jobs()) == 1 and not NotificationSettings.objects.exists()  # planning reads, it never writes
