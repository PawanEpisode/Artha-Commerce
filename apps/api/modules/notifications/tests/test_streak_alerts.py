"""
The streak-at-risk alert (X-01.1 W3.2): a calendar alert made by the sweep. It goes to a student whose streak ends at
yesterday and whose goal is not met today, once a day, 90 minutes before their day ends (earlier when quiet hours begin in
the evening), and never when the goal is met. No network: `FakeChannel` records pushes.
"""

import json
import logging
import uuid
from datetime import UTC, date, datetime, timedelta

import pytest

from modules.notifications.models import Delivery, Notification, NotificationSettings, Preference
from modules.notifications.scheduling import sweep
from modules.notifications.tests.helpers import register
from modules.notifications.tests.tracker_bench import OTHER, USER, rollup
from modules.tracking.models import Goal

pytestmark = pytest.mark.django_db
TODAY = date(2026, 10, 5)
# With the default quiet hours (22:00 to 07:00) the day ends at 22:00 and the window is 20:30 to 22:00 in India.
WINDOW_OPENS = datetime(2026, 10, 5, 15, 0, tzinfo=UTC)  # 20:30 in India
QUIET_STARTS = datetime(2026, 10, 5, 16, 30, tzinfo=UTC)  # 22:00 in India
# Without quiet hours the window is 22:30 to midnight.
LATE_OPENS = datetime(2026, 10, 5, 17, 0, tzinfo=UTC)  # 22:30 in India


@pytest.fixture(autouse=True)
def device():
    return register(USER, platform="android", browser="chrome").device


def streak_notifications(user=None):
    qs = Notification.objects.filter(event="streak_at_risk")
    return qs.filter(user_id=user) if user else qs


def pushed(fake_push):
    out = []
    for _, message in fake_push.sent:
        payload = json.loads(message.body)
        out.append((payload["title"], payload["body"], payload["url"].split("?")[0]))
    return out


def met_yesterday(user=USER, days=3, minutes=130, **kw):
    for n in range(1, days + 1):
        rollup(user, TODAY - timedelta(days=n), minutes, **kw)


# --- who gets it and when ------------------------------------------------------------------------------------------


def test_a_student_with_a_streak_and_an_open_goal_gets_one_alert_when_the_window_opens(fake_push):
    met_yesterday()
    rollup(USER, TODAY, 40)
    run = sweep.run_sweep(now=WINDOW_OPENS)
    assert (run.fired, run.failed) == (1, 0)
    assert pushed(fake_push) == [("Keep your 3-day streak", "1 h 20 min more today meets your goal.", "/app/tracker")]
    n = streak_notifications().get()
    assert (n.dedupe_key, n.category, n.priority) == ("streak:2026-10-05", "tracker", 1)
    assert abs(n.expires_at - (WINDOW_OPENS + timedelta(hours=3))) < timedelta(seconds=1)  # three hours from creation


def test_the_alert_is_not_sent_before_the_window_opens(fake_push):
    met_yesterday()
    sweep.run_sweep(now=WINDOW_OPENS - timedelta(minutes=1))
    assert fake_push.sent == [] and not streak_notifications().exists()


def test_with_default_quiet_hours_it_is_not_created_after_they_begin(fake_push):
    met_yesterday()
    sweep.run_sweep(now=QUIET_STARTS)  # 22:00 sharp: the day has ended for this student
    assert fake_push.sent == [] and not streak_notifications().exists()


def test_without_quiet_hours_the_window_is_the_last_ninety_minutes_before_midnight(fake_push):
    NotificationSettings.objects.create(user_id=USER, quiet_enabled=False)
    met_yesterday()
    sweep.run_sweep(now=LATE_OPENS - timedelta(minutes=1))
    assert fake_push.sent == []
    sweep.run_sweep(now=LATE_OPENS)
    assert len(fake_push.sent) == 1
    assert Delivery.objects.get().lateness_ms < 1000  # measured from the moment the window opened


def test_a_student_whose_quiet_hours_start_later_gets_it_ninety_minutes_before_that(fake_push):
    NotificationSettings.objects.create(user_id=USER, quiet_start="23:00", quiet_end="06:00")
    met_yesterday()
    sweep.run_sweep(now=datetime(2026, 10, 5, 15, 59, tzinfo=UTC))  # 21:29 in India
    assert fake_push.sent == []
    sweep.run_sweep(now=datetime(2026, 10, 5, 16, 0, tzinfo=UTC))  # 21:30: ninety minutes before 23:00
    assert len(fake_push.sent) == 1


def test_it_is_skipped_when_the_goal_is_met(fake_push):
    met_yesterday()
    rollup(USER, TODAY, 120)  # exactly the default goal of two hours
    sweep.run_sweep(now=WINDOW_OPENS)
    assert fake_push.sent == [] and not streak_notifications().exists()


def test_it_stops_the_moment_the_goal_is_met_even_after_the_window_opened(fake_push):
    met_yesterday()
    sweep.run_sweep(now=WINDOW_OPENS - timedelta(minutes=1))
    rollup(USER, TODAY, 125)
    sweep.run_sweep(now=WINDOW_OPENS + timedelta(minutes=10))
    assert fake_push.sent == []


def test_without_a_streak_there_is_nothing_to_lose(fake_push):
    rollup(USER, TODAY - timedelta(days=1), 119)  # yesterday's goal was missed
    rollup(USER, TODAY - timedelta(days=2), 200)
    sweep.run_sweep(now=WINDOW_OPENS)
    assert fake_push.sent == []


def test_the_students_own_goal_decides(fake_push):
    Goal.objects.create(
        user_id=USER, period="daily", subject_key="", target_minutes=30, effective_from=TODAY - timedelta(days=9)
    )
    rollup(USER, TODAY - timedelta(days=1), 45)
    rollup(USER, TODAY, 10)
    sweep.run_sweep(now=WINDOW_OPENS)
    assert pushed(fake_push)[0][1] == "20 min more today meets your goal."


def test_a_streak_of_one_day_reads_naturally(fake_push):
    met_yesterday(days=1)
    sweep.run_sweep(now=WINDOW_OPENS)
    assert pushed(fake_push)[0][0] == "Keep your streak going"


# --- once a day, safe on retry -------------------------------------------------------------------------------------


def test_the_sweep_runs_every_minute_and_the_student_hears_once(fake_push):
    met_yesterday()
    for minute in range(0, 60):
        sweep.run_sweep(now=WINDOW_OPENS + timedelta(minutes=minute))
    assert len(fake_push.sent) == 1 and streak_notifications().count() == 1 and Delivery.objects.count() == 1


def test_the_next_evening_is_a_new_alert(fake_push):
    met_yesterday()
    sweep.run_sweep(now=WINDOW_OPENS)
    next_day = TODAY + timedelta(days=1)
    rollup(USER, TODAY, 130)
    sweep.run_sweep(now=WINDOW_OPENS + timedelta(days=1))
    assert [n.dedupe_key for n in streak_notifications().order_by("created_at")] == [
        "streak:2026-10-05",
        f"streak:{next_day}",
    ]
    assert len(fake_push.sent) == 2


def test_an_alert_that_was_created_but_never_sent_is_sent_by_the_next_run(fake_push, monkeypatch):
    met_yesterday()
    from modules.notifications.services import notify as notify_service

    real_deliver = notify_service.deliver
    monkeypatch.setattr(notify_service, "deliver", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("down")))
    sweep.run_sweep(now=WINDOW_OPENS)
    assert streak_notifications().count() == 1 and fake_push.sent == [] and not Delivery.objects.exists()
    monkeypatch.setattr(notify_service, "deliver", real_deliver)
    sweep.run_sweep(now=WINDOW_OPENS + timedelta(minutes=1))
    assert len(fake_push.sent) == 1 and streak_notifications().count() == 1


def test_a_failure_for_one_student_does_not_stop_the_others(fake_push, monkeypatch, caplog):
    caplog.set_level(logging.ERROR)
    register(OTHER, platform="android", browser="chrome")
    met_yesterday()
    met_yesterday(user=OTHER)
    from modules.notifications.services import notify as notify_service

    real = notify_service.deliver

    def flaky(notification, **kw):
        if notification.user_id == USER:
            raise RuntimeError("down")
        return real(notification, **kw)

    monkeypatch.setattr(notify_service, "deliver", flaky)
    run = sweep.run_sweep(now=WINDOW_OPENS)
    assert run.fired == 1 and [d.user_id for d in Delivery.objects.all()] == [OTHER]
    assert [r.push["error_type"] for r in caplog.records if r.getMessage().startswith("streak_alert_failed")] == [
        "RuntimeError"
    ]


def test_the_step_respects_the_sweeps_job_budget(fake_push):
    for _ in range(5):
        student = uuid.uuid4()
        register(student, platform="android", browser="chrome")
        met_yesterday(user=student)
    run = sweep.run_sweep(now=WINDOW_OPENS, max_jobs=2)
    assert run.fired == 2 and run.more is True
    sweep.run_sweep(now=WINDOW_OPENS + timedelta(minutes=1))
    assert streak_notifications().count() == 5


# --- the rest of the policy ----------------------------------------------------------------------------------------


def test_the_tracker_category_switched_off_records_the_alert_but_sends_nothing(fake_push):
    Preference.objects.create(user_id=USER, category="tracker", channel="push", enabled=False)
    met_yesterday()
    sweep.run_sweep(now=WINDOW_OPENS)
    assert fake_push.sent == []
    assert Delivery.objects.get().suppress_reason == "preference"


def test_a_student_without_a_device_gets_a_record_but_no_push(fake_push):
    student = uuid.uuid4()
    met_yesterday(user=student)
    sweep.run_sweep(now=WINDOW_OPENS)
    assert Delivery.objects.get(notification__user_id=student).suppress_reason == "no_device"


def test_the_daily_cap_applies(fake_push):
    from modules.notifications.models import Device

    d = Device.objects.get(user_id=USER)
    for i in range(4):
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
            sent_at=WINDOW_OPENS - timedelta(hours=1),
            attempted_at=WINDOW_OPENS - timedelta(hours=1),
        )
    met_yesterday()
    sweep.run_sweep(now=WINDOW_OPENS)
    assert Delivery.objects.get(notification__event="streak_at_risk").suppress_reason == "cap" and fake_push.sent == []


def test_nothing_happens_while_the_feature_is_off_or_the_event_is_switched_off(fake_push, settings):
    met_yesterday()
    settings.NOTIFICATIONS_ENABLED = False
    sweep.run_sweep(now=WINDOW_OPENS)
    settings.NOTIFICATIONS_ENABLED = True
    settings.NOTIFICATIONS_DISABLED_EVENTS = ["streak_at_risk"]
    sweep.run_sweep(now=WINDOW_OPENS)
    assert not streak_notifications().exists() and fake_push.sent == []


def test_the_sending_flag_is_strict_so_a_student_without_it_gets_no_record_at_all(fake_push, monkeypatch):
    met_yesterday()
    monkeypatch.setattr("modules.notifications.flags.flag_enabled", lambda *a, **k: False)
    run = sweep.run_sweep(now=WINDOW_OPENS)
    assert run.fired == 0 and not streak_notifications().exists()


def test_the_flag_is_asked_per_student(fake_push, monkeypatch):
    register(OTHER, platform="android", browser="chrome")
    met_yesterday()
    met_yesterday(user=OTHER)
    monkeypatch.setattr("modules.notifications.flags.flag_enabled", lambda name, user_id, **k: user_id == USER)
    sweep.run_sweep(now=WINDOW_OPENS)
    assert [n.user_id for n in streak_notifications()] == [USER] and len(fake_push.sent) == 1


# --- per student ---------------------------------------------------------------------------------------------------


def test_each_student_is_judged_on_their_own_day_and_their_own_quiet_hours(fake_push):
    register(OTHER, platform="android", browser="chrome")
    NotificationSettings.objects.create(user_id=OTHER, quiet_enabled=False)
    met_yesterday()
    met_yesterday(user=OTHER)
    sweep.run_sweep(now=WINDOW_OPENS)  # 20:30 in India: open for the early sleeper, not yet for the other
    assert [n.user_id for n in streak_notifications()] == [USER]
    sweep.run_sweep(now=LATE_OPENS)  # 22:30: the early sleeper's day has ended; the other student's window opens
    assert sorted(n.user_id for n in streak_notifications()) == sorted([USER, OTHER])
    assert Delivery.objects.get(notification__user_id=OTHER).status == "sent"


def test_a_student_in_another_time_zone_gets_it_in_their_own_evening(fake_push):
    register(OTHER, platform="android", browser="chrome")
    NotificationSettings.objects.create(user_id=OTHER, timezone="America/New_York", quiet_enabled=False)
    met_yesterday(user=OTHER, tz="America/New_York")
    sweep.run_sweep(now=WINDOW_OPENS)  # morning in New York
    assert not streak_notifications().exists()
    sweep.run_sweep(now=datetime(2026, 10, 6, 2, 30, tzinfo=UTC))  # 22:30 on Monday 5 Oct in New York
    n = streak_notifications().get()
    assert (n.user_id, n.dedupe_key) == (OTHER, "streak:2026-10-05")


def test_an_alert_never_carries_another_students_numbers(fake_push):
    register(OTHER, platform="android", browser="chrome")
    met_yesterday(days=5)  # a five-day streak
    met_yesterday(user=OTHER, days=2)
    sweep.run_sweep(now=WINDOW_OPENS)
    titles = {n.user_id: n.title for n in streak_notifications()}
    assert titles == {USER: "Keep your 5-day streak", OTHER: "Keep your 2-day streak"}
