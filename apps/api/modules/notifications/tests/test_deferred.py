"""
Deferred delivery (FR-N33): a push held by quiet hours is sent at the end of the window, or dropped if its `expires_at`
has passed. The job asks `dispatch` again when it fires, so every rule is judged at the moment of sending. No network:
`NullQueue` records queue calls and `FakeChannel` records pushes.
"""

import json
import logging
import uuid
from datetime import UTC, datetime, timedelta

import pytest

from modules.notifications import dispatch as dispatch_module
from modules.notifications.channels import ChannelNotConfigured
from modules.notifications.domain.enums import JobKind, JobStatus
from modules.notifications.domain.policy import Action
from modules.notifications.errors import TransientJobError
from modules.notifications.models import Delivery, Notification, NotificationSettings, Preference, ScheduledJob
from modules.notifications.scheduling import jobs, planning, sweep
from modules.notifications.services import notify as notify_service
from modules.notifications.tests.helpers import register

pytestmark = pytest.mark.django_db
USER, OTHER = uuid.uuid4(), uuid.uuid4()
NIGHT = datetime(2026, 10, 5, 18, 0, tzinfo=UTC)  # 23:30 in India: inside the default quiet hours (22:00 to 07:00)
MORNING = datetime(2026, 10, 6, 1, 30, tzinfo=UTC)  # 07:00 in India: the window ends


@pytest.fixture(autouse=True)
def device():
    return register(USER, platform="android", browser="chrome").device


def held(
    event="revision_due", *, user=USER, expires_in=timedelta(hours=12), now=NIGHT, title="Revision due"
) -> Notification:
    """A stored notification the way `create_notification` would leave it (the event has no copy builder yet)."""
    from modules.notifications.domain.catalogue import get_event

    spec = get_event(event)
    return Notification.objects.create(
        user_id=user,
        category=spec.category.value,
        event=event,
        dedupe_key=f"{event}:{uuid.uuid4().hex}",
        title=title,
        body="Three chapters are due.",
        deep_link="/app/revision",
        tag="revision",
        priority=spec.priority,
        expires_at=now + expires_in if expires_in else None,
    )


def deferred_jobs(user=USER):
    return list(ScheduledJob.objects.filter(user_id=user, kind=JobKind.DELIVER_DEFERRED).order_by("expected_version"))


def titles(fake_push):
    return [json.loads(message.body)["title"] for _, message in fake_push.sent]


def log_lines(caplog, name):
    return [r for r in caplog.records if r.getMessage().startswith(name + " ")]


# --- holding -------------------------------------------------------------------------------------------------------


def test_a_push_in_quiet_hours_is_held_and_a_job_is_planned_for_the_end_of_the_window(fake_push, fake_queue, caplog):
    caplog.set_level(logging.INFO)
    n = held()
    result = notify_service.deliver(n, now=NIGHT)
    assert (result.action, result.deliver_at) == (Action.DEFER, MORNING)
    (job,) = deferred_jobs()
    assert (job.subject_key, job.expected_version, job.fire_at, job.status) == (
        str(n.id),
        0,
        MORNING,
        JobStatus.PENDING,
    )
    assert job.context == {"event": "revision_due"} and fake_queue.published == [(job.id, MORNING)]
    assert fake_push.sent == []
    (row,) = Delivery.objects.filter(notification=n)
    assert (row.status, row.device_id, row.suppress_reason) == ("queued", None, None)
    (line,) = log_lines(caplog, "push_deferred")
    assert line.push["event"] == "revision_due" and line.push["wait_ms"] == int(7.5 * 3600 * 1000)  # 23:30 to 07:00


def test_holding_twice_plans_one_job_and_publishes_once(fake_queue):
    n = held()
    notify_service.deliver(n, now=NIGHT)
    notify_service.deliver(n, now=NIGHT + timedelta(minutes=1))
    assert len(deferred_jobs()) == 1 and len(fake_queue.published) == 1


def test_a_held_notification_is_already_readable_in_the_inbox_until_it_expires(fake_push):
    from modules.notifications.selectors import list_inbox

    n = held()
    notify_service.deliver(n, now=NIGHT)
    rows, _ = list_inbox(USER, now=NIGHT)
    assert [row.id for row in rows] == [n.id]
    rows, _ = list_inbox(USER, now=n.expires_at + timedelta(seconds=1))
    assert rows == []


# --- sending at the end of the window ------------------------------------------------------------------------------


def test_the_job_sends_at_the_end_of_the_window_and_the_held_row_becomes_the_sent_one(fake_push):
    n = held()
    notify_service.deliver(n, now=NIGHT)
    (job,) = deferred_jobs()
    result = jobs.fire_job(job.id, now=MORNING)
    assert (result.outcome, result.delivery) == (jobs.FireOutcome.NOTIFIED, "sent")
    assert titles(fake_push) == ["Revision due"]
    (row,) = Delivery.objects.filter(notification=n)
    assert row.status == "sent" and row.device is not None and row.counts_toward_cap
    assert row.lateness_ms == 0  # measured against the moment it was due, not the hour it was created
    job.refresh_from_db()
    assert job.status == JobStatus.FIRED and job.attempts == 1


def test_it_arrives_at_seven_in_the_morning_or_never_per_the_expiry(fake_push):
    alive = held(expires_in=timedelta(hours=12))  # still worth sending at 07:00
    doomed = held(expires_in=timedelta(hours=6))  # expires at 05:30 in India, before the window ends
    assert notify_service.deliver(alive, now=NIGHT).action is Action.DEFER
    result = notify_service.deliver(doomed, now=NIGHT)
    assert (result.action, result.reason.value) == (Action.SUPPRESS, "quiet_hours")
    assert [j.subject_key for j in deferred_jobs()] == [
        str(alive.id)
    ]  # nothing is planned for a push that cannot arrive
    jobs.fire_job(deferred_jobs()[0].id, now=MORNING)
    assert len(fake_push.sent) == 1


def test_a_job_that_fires_after_the_expiry_drops_the_push(fake_push):
    n = held(expires_in=timedelta(hours=8))  # expires 07:30 in India, the window ends 07:00
    notify_service.deliver(n, now=NIGHT)
    (job,) = deferred_jobs()
    result = jobs.fire_job(job.id, now=n.expires_at + timedelta(minutes=1))  # the queue and the sweep were both late
    assert (result.outcome, result.reason, result.delivery) == (jobs.FireOutcome.SKIPPED, "stale", "suppressed")
    assert fake_push.sent == []
    (row,) = Delivery.objects.filter(notification=n)
    assert (row.status, row.suppress_reason, row.device_id) == ("suppressed", "stale", None)
    job.refresh_from_db()
    assert (job.status, job.skip_reason) == (JobStatus.SKIPPED, "stale")


# --- everything is judged again when the job fires -----------------------------------------------------------------


def test_quiet_hours_that_were_moved_hold_it_again_with_a_new_job_version(fake_push):
    n = held()
    notify_service.deliver(n, now=NIGHT)
    NotificationSettings.objects.create(user_id=USER, quiet_start="01:00", quiet_end="09:00")  # moved later in the day
    (first,) = deferred_jobs()
    result = jobs.fire_job(first.id, now=MORNING)
    assert result.delivery == "deferred" and fake_push.sent == []
    first_row, second = deferred_jobs()
    assert (first_row.status, second.expected_version, second.status) == (JobStatus.FIRED, 1, JobStatus.PENDING)
    assert second.fire_at == datetime(2026, 10, 6, 3, 30, tzinfo=UTC)  # 09:00 in India
    assert jobs.fire_job(second.id, now=second.fire_at).delivery == "sent"
    assert len(fake_push.sent) == 1


def test_a_notification_cannot_be_held_for_ever(fake_push, caplog):
    caplog.set_level(logging.WARNING)
    n = held(expires_in=timedelta(days=30))
    notify_service.deliver(n, now=NIGHT)
    for _ in range(planning.MAX_DEFERRALS + 2):
        pending = [j for j in deferred_jobs() if j.status == JobStatus.PENDING]
        if not pending:
            break
        local = pending[0].fire_at + timedelta(
            hours=5, minutes=30
        )  # the student keeps moving quiet hours past the moment
        NotificationSettings.objects.update_or_create(
            user_id=USER,
            defaults={
                "quiet_start": (local - timedelta(hours=1)).time(),
                "quiet_end": (local + timedelta(hours=1)).time(),
            },
        )
        jobs.fire_job(pending[0].id, now=pending[0].fire_at)
    assert len(deferred_jobs()) == planning.MAX_DEFERRALS and fake_push.sent == []
    assert log_lines(caplog, "job_deferral_limit")


def test_switching_the_category_off_while_it_is_held_drops_it(fake_push):
    n = held()
    notify_service.deliver(n, now=NIGHT)
    Preference.objects.create(user_id=USER, category="revision", channel="push", enabled=False)
    jobs.fire_job(deferred_jobs()[0].id, now=MORNING)
    assert fake_push.sent == []
    (row,) = Delivery.objects.filter(notification=n)
    assert (row.status, row.suppress_reason) == ("suppressed", "preference")


def test_switching_push_off_for_everything_while_it_is_held_drops_it(fake_push):
    n = held()
    notify_service.deliver(n, now=NIGHT)
    NotificationSettings.objects.create(user_id=USER, push_master=False)
    jobs.fire_job(deferred_jobs()[0].id, now=MORNING)
    assert fake_push.sent == [] and Delivery.objects.get(notification=n).suppress_reason == "preference"


def test_removing_the_device_while_it_is_held_leaves_nothing_to_send(fake_push, device):
    from modules.notifications.services import devices as device_service

    n = held()
    notify_service.deliver(n, now=NIGHT)
    device_service.remove_device(USER, device.id)
    jobs.fire_job(deferred_jobs()[0].id, now=MORNING)
    assert fake_push.sent == [] and Delivery.objects.get(notification=n).suppress_reason == "no_device"


def test_the_daily_cap_is_judged_at_the_moment_of_sending(fake_push):
    from modules.notifications.models import Device

    n = held()
    notify_service.deliver(n, now=NIGHT)
    d = Device.objects.get(user_id=USER)
    for _ in range(3):
        other = held("daily_nudge", now=MORNING)
        Delivery.objects.create(
            notification=other,
            user_id=USER,
            device=d,
            channel="push",
            status="sent",
            counts_toward_cap=True,
            sent_at=MORNING - timedelta(minutes=5),
            attempted_at=MORNING - timedelta(minutes=5),
        )
    jobs.fire_job(deferred_jobs()[0].id, now=MORNING)
    assert fake_push.sent == [] and Delivery.objects.get(notification=n, device=None).suppress_reason == "cap"


# --- the kill switches ---------------------------------------------------------------------------------------------


def test_the_event_kill_switch_stops_a_held_push_and_says_so_on_its_row(fake_push, settings, caplog):
    caplog.set_level(logging.INFO)
    n = held()
    notify_service.deliver(n, now=NIGHT)
    settings.NOTIFICATIONS_DISABLED_EVENTS = ["revision_due"]
    result = jobs.fire_job(deferred_jobs()[0].id, now=MORNING)
    assert (result.outcome, result.reason) == (jobs.FireOutcome.SKIPPED, "disabled")
    assert fake_push.sent == []
    (row,) = Delivery.objects.filter(notification=n)
    assert (row.status, row.suppress_reason) == ("suppressed", "flag_off")  # not left `queued` for ever
    assert log_lines(caplog, "push_suppressed")


def test_a_kill_switch_for_another_event_does_not_stop_it(fake_push, settings):
    settings.NOTIFICATIONS_DISABLED_EVENTS = ["daily_nudge"]
    notify_service.deliver(held(), now=NIGHT)
    assert jobs.fire_job(deferred_jobs()[0].id, now=MORNING).delivery == "sent"


def test_the_sending_flag_is_strict_when_the_job_fires(fake_push, monkeypatch):
    n = held()
    notify_service.deliver(n, now=NIGHT)
    monkeypatch.setattr("modules.notifications.flags.flag_enabled", lambda *a, **k: False)
    result = jobs.fire_job(deferred_jobs()[0].id, now=MORNING)
    assert (result.outcome, result.reason) == (jobs.FireOutcome.SKIPPED, "flag_off")
    assert fake_push.sent == [] and Delivery.objects.get(notification=n).suppress_reason == "flag_off"


def test_the_environment_switch_stops_it_too(fake_push, settings):
    notify_service.deliver(held(), now=NIGHT)
    settings.NOTIFICATIONS_ENABLED = False
    assert jobs.fire_job(deferred_jobs()[0].id, now=MORNING).reason == "disabled" and fake_push.sent == []


# --- idempotent and safe on retry ----------------------------------------------------------------------------------


def test_two_fires_of_one_job_send_once(fake_push):
    notify_service.deliver(held(), now=NIGHT)
    (job,) = deferred_jobs()
    first = jobs.fire_job(job.id, now=MORNING)
    again = jobs.fire_job(job.id, now=MORNING + timedelta(seconds=1))
    assert first.delivery == "sent" and again.outcome is jobs.FireOutcome.IGNORED
    assert len(fake_push.sent) == 1 and Delivery.objects.filter(status="sent").count() == 1


def test_a_job_whose_send_raised_goes_back_to_pending_and_sends_once_on_the_retry(fake_push, monkeypatch):
    n = held()
    notify_service.deliver(n, now=NIGHT)
    (job,) = deferred_jobs()
    real_send = fake_push.send
    monkeypatch.setattr(fake_push, "send", lambda *a, **k: (_ for _ in ()).throw(ChannelNotConfigured("no keys")))
    with pytest.raises(TransientJobError):
        jobs.fire_job(job.id, now=MORNING)
    job.refresh_from_db()
    assert (job.status, job.attempts, job.fired_at) == (JobStatus.PENDING, 1, None) and fake_push.sent == []
    monkeypatch.setattr(fake_push, "send", real_send)
    assert jobs.fire_job(job.id, now=MORNING + timedelta(seconds=30)).delivery == "sent"
    assert len(fake_push.sent) == 1


def test_a_job_that_keeps_failing_gives_up_after_three_attempts(fake_push, monkeypatch):
    notify_service.deliver(held(), now=NIGHT)
    (job,) = deferred_jobs()
    monkeypatch.setattr(fake_push, "send", lambda *a, **k: (_ for _ in ()).throw(ChannelNotConfigured("no keys")))
    for _ in range(3):
        with pytest.raises(TransientJobError):
            jobs.fire_job(job.id, now=MORNING)
    job.refresh_from_db()
    assert (job.status, job.attempts) == (JobStatus.FAILED, 3)


def test_a_push_that_already_reached_every_device_is_not_sent_again(fake_push):
    n = held()
    notify_service.deliver(n, now=NIGHT)
    (job,) = deferred_jobs()
    dispatch_module.dispatch(n, now=MORNING)  # something else delivered it first (a replayed event)
    assert len(fake_push.sent) == 1
    result = jobs.fire_job(job.id, now=MORNING + timedelta(seconds=5))
    assert result.delivery == "already_sent" and len(fake_push.sent) == 1


def test_the_sweep_sends_a_held_push_whose_queue_message_never_arrived(fake_push):
    notify_service.deliver(held(), now=NIGHT)
    run = sweep.run_sweep(now=MORNING + timedelta(minutes=1))
    assert (run.fired, len(fake_push.sent)) == (1, 1)


def test_the_sweep_leaves_a_held_push_alone_until_its_time(fake_push):
    notify_service.deliver(held(), now=NIGHT)
    run = sweep.run_sweep(now=MORNING - timedelta(minutes=1))
    assert run.handled == 0 and fake_push.sent == []


# --- per student ---------------------------------------------------------------------------------------------------


def test_a_job_can_only_deliver_its_own_students_notification(fake_push):
    register(OTHER, platform="android", browser="chrome")
    mine = held(user=USER)
    notify_service.deliver(mine, now=NIGHT)
    # A job planned for another student that names my notification finds nothing of theirs and sends nothing.
    stray = ScheduledJob.objects.create(
        user_id=OTHER,
        kind=JobKind.DELIVER_DEFERRED,
        subject_key=str(mine.id),
        fire_at=MORNING,
        context={"event": "revision_due"},
    )
    result = jobs.fire_job(stray.id, now=MORNING)
    assert (result.outcome, result.reason) == (jobs.FireOutcome.SKIPPED, "gone") and fake_push.sent == []


def test_each_students_quiet_hours_decide_their_own_hold(fake_push):
    register(OTHER, platform="android", browser="chrome")
    NotificationSettings.objects.create(user_id=OTHER, quiet_enabled=False)
    mine, theirs = held(user=USER), held(user=OTHER)
    assert notify_service.deliver(mine, now=NIGHT).action is Action.DEFER
    assert notify_service.deliver(theirs, now=NIGHT).action is Action.SEND
    assert len(fake_push.sent) == 1 and [j.user_id for j in deferred_jobs(OTHER)] == []


def test_a_notification_that_was_erased_while_held_is_gone(fake_push):
    n = held()
    notify_service.deliver(n, now=NIGHT)
    (job,) = deferred_jobs()
    Notification.objects.filter(pk=n.pk).delete()
    result = jobs.fire_job(job.id, now=MORNING)
    assert (result.outcome, result.reason) == (jobs.FireOutcome.SKIPPED, "gone") and fake_push.sent == []


def test_a_job_with_a_subject_that_is_not_a_notification_id_is_gone_not_a_crash(fake_push):
    junk = ScheduledJob.objects.create(
        user_id=USER, kind=JobKind.DELIVER_DEFERRED, subject_key="not-a-uuid", fire_at=MORNING, context={"event": "x"}
    )
    assert jobs.fire_job(junk.id, now=MORNING).reason == "gone"


def test_timer_alerts_are_never_held(fake_push):
    from modules.notifications.domain.catalogue import get_event

    spec = get_event("timer_end")
    n = Notification.objects.create(
        user_id=USER,
        category="timer",
        event="timer_end",
        dedupe_key="timer_end:x:1",
        title="Round 1 done",
        body="x",
        deep_link="/app/focus",
        priority=spec.priority,
    )
    assert notify_service.deliver(n, now=NIGHT).outcome == "sent" and deferred_jobs() == []
