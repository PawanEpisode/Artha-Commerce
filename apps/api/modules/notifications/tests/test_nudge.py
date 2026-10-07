"""
The daily nudge (W3.3, FR-N10): a sweep step that finds due students and sends exactly one push to those who have not
opened the app today, through the normal policy (preferences, quiet hours, cap, switches), once per local day.
"""

import json
import logging
import uuid
from datetime import UTC, date, datetime, time, timedelta

import pytest

from modules.notifications.domain.enums import DeliveryStatus, JobStatus
from modules.notifications.models import (
    Delivery,
    MessageShown,
    Notification,
    NotificationSettings,
    Preference,
    ScheduledJob,
)
from modules.notifications.scheduling import sweep
from modules.notifications.services import nudge as nudge_service
from modules.notifications.services import permission as permission_service
from modules.notifications.services import settings as settings_service
from modules.notifications.services import thought as thought_service
from modules.notifications.tests.helpers import register
from modules.notifications.tests.motivation_helpers import OTHER, THIRD, USER, library, message
from modules.profiles.models import LastVisit

pytestmark = pytest.mark.django_db

PLANNED = datetime(2026, 10, 6, 12, 0, tzinfo=UTC)  # settings written on Tuesday 17:30 in India
DUE = datetime(2026, 10, 7, 4, 30, tzinfo=UTC)  # so the nudge falls due Wednesday 10:00 in India
AT = DUE + timedelta(seconds=40)  # the minute's sweep
NEXT = DUE + timedelta(days=1)


@pytest.fixture(autouse=True)
def device():
    return register(USER, platform="android", browser="chrome").device


@pytest.fixture(autouse=True)
def lines():
    return library(12)


def plan(user=USER, **changes):
    """The student's notification settings, written the way the settings screen writes them."""
    return settings_service.update_settings(user, changes, now=PLANNED)


def run(now=AT, **kwargs):
    return sweep.run_sweep(now=now, **kwargs)


def nudges(user=USER):
    return Notification.objects.filter(event="daily_nudge", user_id=user)


def pushed(fake_push):
    return [json.loads(message.body) for _, message in fake_push.sent]


def visit(at, user=USER):
    LastVisit.objects.update_or_create(user_id=user, defaults={"path": "/app", "search": "", "visited_at": at})


def log_lines(caplog, name):
    return [r for r in caplog.records if r.getMessage().startswith(name + " ")]


def next_at(user=USER):
    return NotificationSettings.objects.get(user_id=user).next_nudge_at


# --- a student who did not open the app gets exactly one ---------------------------------------------------------------


def test_a_due_student_who_has_not_opened_the_app_gets_one_push_with_a_library_line(fake_push):
    plan()
    assert next_at() == DUE
    result = run()
    assert (result.fired, result.skipped, result.failed) == (1, 0, 0)

    (payload,) = pushed(fake_push)
    shown = MessageShown.objects.get()
    assert payload["title"] == "A thought for today" and payload["body"] == shown.message.body
    assert payload["url"].split("?")[0] == "/app" and payload["tag"] == "nudge:2026-10-07"

    n = nudges().get()
    assert (n.dedupe_key, n.category, n.priority, n.deep_link) == ("nudge:2026-10-07", "motivation", 3, "/app")
    assert n.context["message"] == shown.message.body
    assert (shown.user_id, shown.shown_on, shown.channel) == (USER, date(2026, 10, 7), "push")
    d = Delivery.objects.get(notification=n)
    assert (d.status, d.channel, d.counts_toward_cap) == (DeliveryStatus.SENT, "push", True)
    assert next_at() == NEXT  # the next one is tomorrow at 10:00


def test_running_the_sweep_again_and_again_sends_nothing_more(fake_push):
    plan()
    run()
    for later in (AT + timedelta(minutes=1), AT + timedelta(minutes=30), AT + timedelta(hours=5)):
        assert run(later).fired == 0
    assert len(fake_push.sent) == 1 and nudges().count() == 1


def test_two_workers_cannot_both_claim_the_same_due_time(fake_push):
    plan()
    assert nudge_service.process_due_nudge(USER, now=AT) is nudge_service.NudgeOutcome.NOTIFIED
    assert nudge_service.process_due_nudge(USER, now=AT) is nudge_service.NudgeOutcome.NOT_DUE
    assert len(fake_push.sent) == 1


def test_a_student_whose_time_has_not_come_is_left_alone(fake_push):
    plan()
    assert run(DUE - timedelta(seconds=1)).fired == 0 and fake_push.sent == [] and not nudges().exists()
    assert next_at() == DUE


def test_the_nudge_uses_the_students_tone(fake_push):
    NotificationSettings.objects.all().delete()
    message("A driven line.", tone="driven")
    plan(nudge_tone="driven")
    run()
    assert pushed(fake_push)[0]["body"] in {"A driven line."}


# --- opened the app today: no push (FR-N10) ---------------------------------------------------------------------------


def test_a_student_who_opened_the_app_at_nine_gets_no_ten_oclock_push(fake_push, caplog):
    caplog.set_level(logging.INFO)
    plan()
    visit(datetime(2026, 10, 7, 3, 30, tzinfo=UTC))  # 09:00 in India
    run()
    assert fake_push.sent == []
    d = Delivery.objects.get()
    assert (d.status, d.suppress_reason, d.device_id) == (DeliveryStatus.SUPPRESSED, "visited_today", None)
    (line,) = log_lines(caplog, "push_suppressed")
    assert line.push == {"event": "daily_nudge", "reason": "visited_today"}
    assert next_at() == NEXT  # tomorrow's nudge is still planned


def test_yesterday_evening_is_not_a_visit_today(fake_push):
    plan()
    visit(datetime(2026, 10, 6, 18, 0, tzinfo=UTC))  # 23:30 yesterday in India
    run()
    assert len(fake_push.sent) == 1


def test_the_local_day_starts_at_midnight_in_the_students_zone(fake_push):
    plan()
    visit(datetime(2026, 10, 6, 18, 29, 59, tzinfo=UTC))  # one second before 00:00 in India
    run()
    assert len(fake_push.sent) == 1
    visit(datetime(2026, 10, 6, 18, 30, tzinfo=UTC), user=OTHER)  # exactly 00:00
    plan(OTHER)
    register(OTHER)
    run(AT + timedelta(minutes=1))
    assert len(fake_push.sent) == 1  # the second student's visit counted: still only the first student's push


def test_opening_the_home_page_counts_even_when_the_tab_was_never_hidden(fake_push, auth_client, clock):
    """The thought card is fetched on the first open of the day, so a student still on the page is not nudged."""
    plan()
    clock.set(datetime(2026, 10, 7, 3, 45, tzinfo=UTC))  # 09:15 in India
    card = auth_client.get("/api/v1/notifications/thought/today/").json()["thought"]
    clock.set(AT)
    run()
    assert fake_push.sent == []
    assert Delivery.objects.get().suppress_reason == "visited_today"
    assert MessageShown.objects.get().message.body == card["body"] and MessageShown.objects.count() == 1


def test_a_message_the_nudge_used_is_not_a_visit(fake_push):
    plan()
    thought_service.reserve_message(USER, local_date=date(2026, 10, 7), tone="calm", channel="push", now=DUE)
    run()
    assert len(fake_push.sent) == 1


def test_a_nudge_that_was_never_sent_for_a_visit_stays_out_of_the_inbox(auth_client, clock):
    plan()
    visit(datetime(2026, 10, 7, 3, 30, tzinfo=UTC))
    run()
    assert nudges().count() == 1
    clock.set(AT)
    body = auth_client.get("/api/v1/notifications/inbox/").json()
    assert body["results"] == [] and body["unread_count"] == 0


def test_a_sent_nudge_shows_in_the_inbox_as_the_daily_thought(auth_client, clock):
    plan()
    run()
    clock.set(AT)
    body = auth_client.get("/api/v1/notifications/inbox/").json()
    assert [(r["category"], r["category_label"], r["deep_link"]) for r in body["results"]] == [
        ("motivation", "Daily thought", "/app")
    ]
    assert body["unread_count"] == 1


# --- every rule of the pipeline applies -----------------------------------------------------------------------------


def test_the_master_switch_off_means_no_nudge(fake_push):
    plan()
    plan(push_master=False)
    assert next_at() is None
    run()
    assert fake_push.sent == [] and not nudges().exists()
    NotificationSettings.objects.filter(user_id=USER).update(next_nudge_at=DUE)  # even a stale time cannot send it
    run()
    assert fake_push.sent == [] and not nudges().exists()


def test_the_nudge_switch_off_means_no_nudge(fake_push):
    plan(nudge_enabled=False)
    run()
    assert fake_push.sent == [] and not nudges().exists()


def test_the_category_switch_off_for_push_suppresses_the_push(fake_push):
    plan()
    Preference.objects.create(user_id=USER, category="motivation", channel="push", enabled=False)
    run()
    assert fake_push.sent == []
    assert Delivery.objects.get().suppress_reason == "preference"


def test_a_student_with_no_device_gets_no_push(fake_push, device):
    plan()
    device.delete()
    run()
    assert fake_push.sent == [] and Delivery.objects.get().suppress_reason == "no_device"


def test_the_inbox_switch_hides_it_from_the_inbox_but_the_push_still_goes(fake_push, auth_client, clock):
    plan()
    Preference.objects.create(user_id=USER, category="motivation", channel="inbox", enabled=False)
    run()
    clock.set(AT)
    assert len(fake_push.sent) == 1
    assert auth_client.get("/api/v1/notifications/inbox/").json()["results"] == []


def test_the_daily_cap_applies(fake_push):
    plan()
    for n in range(3):
        old = Notification.objects.create(
            user_id=USER,
            category="tracker",
            event="goal_reached",
            dedupe_key=f"goal:{n}",
            title="t",
            body="b",
            deep_link="/app/tracker",
            priority=1,
        )
        Delivery.objects.create(
            notification=old,
            user_id=USER,
            channel="push",
            status="sent",
            counts_toward_cap=True,
            attempted_at=DUE - timedelta(hours=2),
            sent_at=DUE - timedelta(hours=2),
        )
    run()
    assert fake_push.sent == [] and nudges().get().deliveries.get().suppress_reason == "cap"


def test_quiet_hours_hold_it_and_it_arrives_once_when_they_end(fake_push):
    plan(nudge_time=time(6, 0))  # inside the default quiet window, 22:00 to 07:00
    due = datetime(2026, 10, 7, 0, 30, tzinfo=UTC)
    assert next_at() == due
    run(due + timedelta(seconds=40))
    assert fake_push.sent == []
    assert nudges().get().deliveries.get().status == DeliveryStatus.QUEUED
    job = ScheduledJob.objects.get(kind="deliver_deferred")
    assert job.fire_at == datetime(2026, 10, 7, 1, 30, tzinfo=UTC)  # 07:00 in India

    run(job.fire_at + timedelta(minutes=1))
    assert len(fake_push.sent) == 1
    run(job.fire_at + timedelta(minutes=2))
    assert len(fake_push.sent) == 1
    assert ScheduledJob.objects.get().status == JobStatus.FIRED


def test_a_student_who_opens_the_app_while_the_nudge_is_held_is_not_pushed_afterwards(fake_push):
    plan(nudge_time=time(6, 0))
    due = datetime(2026, 10, 7, 0, 30, tzinfo=UTC)
    run(due + timedelta(seconds=40))
    visit(datetime(2026, 10, 7, 1, 0, tzinfo=UTC))  # 06:30 in India, before the quiet hours end
    run(datetime(2026, 10, 7, 1, 31, tzinfo=UTC))
    assert fake_push.sent == []
    assert nudges().get().deliveries.get().suppress_reason == "visited_today"


def test_the_kill_switch_for_the_event_stops_it_and_only_it(fake_push, settings):
    plan()
    settings.NOTIFICATIONS_DISABLED_EVENTS = ["daily_nudge"]
    result = run()
    assert (result.fired, result.skipped) == (0, 0) and fake_push.sent == [] and not nudges().exists()
    assert next_at() == DUE  # nothing was claimed: the switch can come back without losing the student

    settings.NOTIFICATIONS_DISABLED_EVENTS = ["streak_at_risk", "goal_reached"]
    assert run().fired == 1


def test_the_environment_switch_off_stops_everything(fake_push, settings):
    plan()
    settings.NOTIFICATIONS_ENABLED = False
    assert run().fired == 0 and fake_push.sent == [] and not nudges().exists()


def test_the_sending_flag_is_strict_and_a_student_outside_it_is_skipped_and_replanned(fake_push, monkeypatch, caplog):
    caplog.set_level(logging.INFO)
    seen = []

    def flag(name, user_id=None, **kwargs):
        seen.append((name, kwargs.get("strict")))
        return name != "notifications_send"

    monkeypatch.setattr("modules.notifications.flags.flag_enabled", flag)
    plan()
    result = run()
    assert ("notifications_send", True) in seen  # strict: unknown or an error means off
    assert (result.fired, result.skipped) == (0, 1) and fake_push.sent == [] and not nudges().exists()
    assert not MessageShown.objects.exists()
    assert next_at() == NEXT
    assert log_lines(caplog, "nudge_skipped")[0].push == {"event": "daily_nudge", "reason": "flag_off"}


def test_the_link_is_on_the_allow_list(fake_push):
    from modules.notifications.domain.deeplinks import is_allowed

    plan()
    run()
    assert is_allowed(nudges().get().deep_link) and is_allowed(pushed(fake_push)[0]["url"].split("?")[0])


# --- one a day, whatever the settings do --------------------------------------------------------------------------


def test_changing_the_time_after_todays_nudge_does_not_send_a_second(fake_push):
    plan()
    run()
    settings_service.update_settings(USER, {"nudge_time": time(18, 0)}, now=AT)  # today's 18:00 is still ahead
    assert next_at() == datetime(2026, 10, 7, 12, 30, tzinfo=UTC)
    result = run(datetime(2026, 10, 7, 12, 31, tzinfo=UTC))
    assert len(fake_push.sent) == 1 and result.skipped == 1 and nudges().count() == 1
    assert next_at() == datetime(2026, 10, 8, 12, 30, tzinfo=UTC)


# --- late and unavailable --------------------------------------------------------------------------------------------


def test_a_nudge_that_was_missed_by_more_than_six_hours_is_dropped_and_replanned(fake_push, caplog):
    caplog.set_level(logging.INFO)
    plan()
    late = DUE + timedelta(hours=6, minutes=1)
    result = run(late)
    assert (result.fired, result.skipped) == (0, 1) and fake_push.sent == [] and not nudges().exists()
    assert next_at() == NEXT  # not a burst of old ones: the next regular time
    assert log_lines(caplog, "nudge_skipped")[0].push["reason"] == "stale"


def test_a_slightly_late_nudge_still_goes(fake_push):
    plan()
    assert run(DUE + timedelta(hours=5)).fired == 1 and len(fake_push.sent) == 1


def test_an_empty_or_fully_seen_library_sends_nothing_and_does_not_repeat(fake_push, caplog):
    caplog.set_level(logging.INFO)
    from modules.notifications.models import Message

    Message.objects.all().delete()
    plan()
    result = run()
    assert (result.fired, result.skipped) == (0, 1) and fake_push.sent == [] and not nudges().exists()
    assert next_at() == NEXT
    assert log_lines(caplog, "motivation_unavailable")[0].push["reason"] == "empty"


def test_the_nudge_never_repeats_a_line_seen_in_the_last_sixty_days(fake_push):
    from modules.notifications.models import Message

    Message.objects.all().delete()
    only = message("The only line.")
    seen = MessageShown.objects.create(
        user_id=USER, message=only, shown_on=date(2026, 8, 10), channel="inapp"
    )  # 58 days ago
    MessageShown.objects.filter(pk=seen.pk).update(created_at=datetime(2026, 8, 10, 6, 0, tzinfo=UTC))
    plan()
    run()
    assert fake_push.sent == [] and nudges().count() == 0
    MessageShown.objects.all().update(shown_on=date(2026, 8, 8))  # 60 days ago: allowed again
    NotificationSettings.objects.filter(user_id=USER).update(next_nudge_at=DUE)
    run(AT + timedelta(minutes=1))
    assert pushed(fake_push)[0]["body"] == "The only line."


# --- many students -----------------------------------------------------------------------------------------------------


def test_each_student_is_isolated_from_the_others_failures(fake_push, monkeypatch, caplog):
    caplog.set_level(logging.ERROR)
    for user in (OTHER, THIRD):
        register(user, platform="android", browser="chrome")
    for user in (USER, OTHER, THIRD):
        plan(user)
    real = thought_service.reserve_message

    def reserve(user_id, **kwargs):
        if user_id == OTHER:
            raise RuntimeError("boom with a secret")
        return real(user_id, **kwargs)

    monkeypatch.setattr(thought_service, "reserve_message", reserve)
    result = run()
    assert (result.fired, result.failed) == (2, 1) and len(fake_push.sent) == 2
    assert {n.user_id for n in Notification.objects.filter(event="daily_nudge")} == {USER, THIRD}
    (line,) = log_lines(caplog, "nudge_failed")
    assert line.push == {"event": "daily_nudge", "error_type": "RuntimeError"} and "secret" not in line.getMessage()


def test_students_get_different_lines_and_their_own_day(fake_push):
    for user in (OTHER, THIRD):
        register(user, platform="android", browser="chrome")
    for user in (USER, OTHER, THIRD):
        plan(user)
    run()
    assert {s.user_id for s in MessageShown.objects.all()} == {USER, OTHER, THIRD}
    assert len(fake_push.sent) == 3


def test_a_batch_is_bounded_and_the_rest_follow_in_later_runs_each_exactly_once(fake_push):
    students = [OTHER, THIRD, USER] + [uuid.uuid4() for _ in range(4)]
    for user in students:
        if user != USER:  # the autouse fixture gave this one a device already
            register(user, platform="android", browser="chrome")
        plan(user)
    first = run(max_jobs=3)
    assert first.fired == 3 and first.more is True
    for minute in range(1, 5):
        run(AT + timedelta(minutes=minute), max_jobs=3)
    assert len(fake_push.sent) == 7 and Notification.objects.filter(event="daily_nudge").count() == 7
    assert {s.user_id for s in MessageShown.objects.all()} == set(students)


def test_the_most_overdue_students_go_first(fake_push):
    early, later = OTHER, THIRD
    for user in (early, later, USER):
        register(user, platform="android", browser="chrome")
        plan(user)
    NotificationSettings.objects.filter(user_id=early).update(next_nudge_at=DUE - timedelta(hours=2))
    NotificationSettings.objects.filter(user_id=later).update(next_nudge_at=DUE - timedelta(hours=1))
    run(max_jobs=1)
    assert [n.user_id for n in Notification.objects.filter(event="daily_nudge")] == [early]


# --- keeping next_nudge_at right ----------------------------------------------------------------------------------


def test_the_permission_journey_gives_a_new_student_a_first_nudge_time():
    permission_service.record_permission_state(USER, "pre_prompt_shown", "onboarding", now=PLANNED)
    assert next_at() == DUE
    NotificationSettings.objects.filter(user_id=USER).update(next_nudge_at=None)
    permission_service.record_permission_state(USER, "granted", "onboarding", now=PLANNED)
    assert next_at() == DUE


def test_the_sweep_heals_rows_that_have_no_nudge_time_yet(fake_push):
    NotificationSettings.objects.create(user_id=USER)  # written before this wave: nudge on, no time
    assert next_at() is None
    run(PLANNED)
    assert next_at() == DUE
    assert fake_push.sent == []  # healed, not sent early
    run(AT)
    assert len(fake_push.sent) == 1


def test_it_leaves_rows_that_want_no_nudge_without_a_time():
    NotificationSettings.objects.create(user_id=USER, nudge_enabled=False)
    NotificationSettings.objects.create(user_id=OTHER, push_master=False)
    assert settings_service.backfill_next_nudges(PLANNED, limit=10) == 0
    assert NotificationSettings.objects.filter(next_nudge_at__isnull=False).count() == 0


def test_changing_the_time_zone_moves_the_next_nudge_to_the_same_local_time_there():
    plan()
    assert next_at() == DUE
    settings_service.update_settings(USER, {"timezone": "Europe/London"}, now=PLANNED)
    assert next_at() == datetime(2026, 10, 7, 9, 0, tzinfo=UTC)  # 10:00 BST tomorrow: today's has passed (13:00 there)
    settings_service.update_settings(USER, {"timezone": "America/New_York"}, now=PLANNED)
    assert next_at() == datetime(2026, 10, 6, 14, 0, tzinfo=UTC)  # 10:00 EDT today is still ahead (08:00 there)


def test_changing_the_nudge_time_moves_it_and_turning_it_off_and_on_replans_it():
    plan()
    settings_service.update_settings(USER, {"nudge_time": time(21, 15)}, now=PLANNED)
    assert next_at() == datetime(2026, 10, 6, 15, 45, tzinfo=UTC)  # tonight: 21:15 in India is still ahead of 17:30
    settings_service.update_settings(USER, {"nudge_enabled": False}, now=PLANNED)
    assert next_at() is None
    settings_service.update_settings(USER, {"nudge_enabled": True}, now=PLANNED)
    assert next_at() == datetime(2026, 10, 6, 15, 45, tzinfo=UTC)


def test_changing_only_the_tone_leaves_the_time_alone():
    plan()
    settings_service.update_settings(USER, {"nudge_tone": "driven"}, now=PLANNED + timedelta(days=3))
    assert next_at() == DUE


# --- daylight saving: the nudge stays at the student's local time ----------------------------------------------------------


def test_a_new_york_student_is_nudged_at_ten_oclock_before_and_after_the_clocks_go_back(fake_push):
    register(OTHER, platform="android", browser="chrome")
    settings_service.update_settings(
        OTHER, {"timezone": "America/New_York"}, now=datetime(2026, 10, 31, 12, 0, tzinfo=UTC)
    )
    friday = datetime(2026, 10, 31, 14, 0, tzinfo=UTC)  # 10:00 EDT
    assert next_at(OTHER) == friday
    run(friday + timedelta(seconds=30))
    assert next_at(OTHER) == datetime(2026, 11, 1, 15, 0, tzinfo=UTC)  # 10:00 EST, the clocks went back overnight
    run(datetime(2026, 11, 1, 15, 0, 30, tzinfo=UTC))
    assert next_at(OTHER) == datetime(2026, 11, 2, 15, 0, tzinfo=UTC)
    assert sorted(nudges(OTHER).values_list("dedupe_key", flat=True)) == ["nudge:2026-10-31", "nudge:2026-11-01"]
    assert len(fake_push.sent) == 2


def test_the_day_of_a_nudge_is_the_students_local_day_not_the_utc_day(fake_push):
    plan(nudge_time=time(0, 15))  # 00:15 in India is 18:45 UTC the evening before
    due = datetime(2026, 10, 6, 18, 45, tzinfo=UTC)
    assert next_at() == due
    run(due + timedelta(seconds=30), max_jobs=5)
    assert nudges().get().dedupe_key == "nudge:2026-10-07"
    assert MessageShown.objects.get().shown_on == date(2026, 10, 7)
