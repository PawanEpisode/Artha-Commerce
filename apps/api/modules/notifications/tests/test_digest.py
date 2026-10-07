"""
Fatigue control and the daily digest (X-01.1 W3.7, FR-N34): the offer appears after five ignored pushes over three days,
once per 30 days; accepting moves every category but the timer to the inbox and sends one digest a day at the nudge
time; stopping it puts the push switches back.
"""

import json
import uuid
from datetime import UTC, date, datetime, time, timedelta

import pytest

from modules.coverage.models import ChapterProgress, Enrollment
from modules.notifications.domain.enums import DeliveryStatus
from modules.notifications.models import Delivery, Notification, NotificationSettings, Preference
from modules.notifications.scheduling import sweep
from modules.notifications.selectors import fatigue as fatigue_selectors
from modules.notifications.services import digest as digest_service
from modules.notifications.services import inbox as inbox_service
from modules.notifications.services import notify as notify_service
from modules.notifications.services import settings as settings_service
from modules.notifications.tests.helpers import register
from modules.notifications.tests.motivation_helpers import USER, library
from modules.syllabus.models import Chapter

pytestmark = pytest.mark.django_db
URL = "/api/v1/notifications/digest/"
PLANNED = datetime(2026, 10, 6, 12, 0, tzinfo=UTC)
DUE = datetime(2026, 10, 7, 4, 30, tzinfo=UTC)  # Wednesday 10:00 in India
AT = DUE + timedelta(seconds=40)
TODAY = date(2026, 10, 7)


@pytest.fixture(autouse=True)
def device():
    return register(USER, platform="android", browser="chrome").device


@pytest.fixture(autouse=True)
def lines():
    return library(12)


def sent_push(at: datetime, *, user=USER, event="goal_reached", clicked=False, counts=True, devices=1) -> Notification:
    n = Notification.objects.create(
        user_id=user,
        category="tracker",
        event=event,
        dedupe_key=f"k:{uuid.uuid4().hex}",
        title="t",
        body="b",
        deep_link="/app/tracker",
        priority=1 if counts else 0,
    )
    for _ in range(devices):
        Delivery.objects.create(
            notification=n,
            user_id=user,
            device=register(user, platform="android").device if devices > 1 else None,
            channel="push",
            status=DeliveryStatus.SENT,
            counts_toward_cap=counts,
            attempted_at=at,
            sent_at=at,
            clicked_at=at if clicked else None,
        )
    return n


def ignored_run(end: datetime = PLANNED, *, count=5, step_hours=13) -> list[Notification]:
    return [sent_push(end - timedelta(hours=step_hours * i)) for i in range(count)]


def offer_due(now=PLANNED) -> bool:
    return fatigue_selectors.digest_offer_due(USER, now=now)


def row() -> NotificationSettings:
    return NotificationSettings.objects.get(user_id=USER)


def push_overrides() -> dict:
    return {(p.category, p.channel): p.enabled for p in Preference.objects.filter(user_id=USER)}


def pushed(fake_push):
    return [json.loads(message.body) for _, message in fake_push.sent]


# --- the offer -----------------------------------------------------------------------------------------------------


def test_five_ignored_pushes_over_three_days_make_the_offer_due():
    ignored_run()
    assert offer_due()


def test_four_are_not_enough_and_a_click_resets():
    pushes = ignored_run(count=4)
    assert not offer_due()
    sent_push(PLANNED - timedelta(days=3))
    assert offer_due()
    inbox_service.mark_clicked(USER, pushes[0].id, now=PLANNED)
    assert not offer_due()


def test_timer_alerts_do_not_count(fake_push):
    ignored_run(count=4)
    for i in range(6):
        sent_push(PLANNED + timedelta(minutes=i), event="timer_end", counts=False)
    assert not offer_due(PLANNED + timedelta(hours=1))


def test_one_push_to_several_devices_counts_once_and_a_click_on_any_device_counts():
    ignored_run(count=4, step_hours=24)
    n = sent_push(PLANNED + timedelta(hours=1), devices=3)
    assert offer_due(PLANNED + timedelta(hours=2))
    second = Delivery.objects.filter(notification=n).order_by("id")[1]
    second.clicked_at = PLANNED
    second.save()
    assert not offer_due(PLANNED + timedelta(hours=2))


def test_seen_records_the_offer_once_and_hides_it_for_30_days():
    ignored_run()
    digest_service.answer(USER, digest_service.Answer.SEEN, now=PLANNED)
    assert row().digest_offered_at == PLANNED and not offer_due()
    digest_service.answer(USER, digest_service.Answer.SEEN, now=PLANNED + timedelta(days=1))
    assert row().digest_offered_at == PLANNED  # not moved: the offer was not due
    assert not offer_due(PLANNED + timedelta(days=29))
    assert offer_due(PLANNED + timedelta(days=30))


def test_seen_when_nothing_is_due_writes_nothing():
    digest_service.answer(USER, digest_service.Answer.SEEN, now=PLANNED)
    assert row().digest_offered_at is None


def test_decline_counts_as_offered_and_changes_nothing_else():
    ignored_run()
    digest_service.answer(USER, digest_service.Answer.DECLINE, now=PLANNED)
    assert row().digest_offered_at == PLANNED and not row().digest_enabled and push_overrides() == {}


# --- accepting and stopping ----------------------------------------------------------------------------------------


def test_accepting_moves_every_category_but_the_timer_to_the_inbox_and_plans_the_digest():
    settings_service.update_settings(USER, {"nudge_enabled": False}, now=PLANNED)
    ignored_run()
    digest_service.answer(USER, digest_service.Answer.ACCEPT, now=PLANNED)
    r = row()
    assert r.digest_enabled and r.nudge_enabled and r.next_nudge_at == DUE and r.digest_offered_at == PLANNED
    prefs = push_overrides()
    assert ("timer", "push") not in prefs
    for category in ("tracker", "revision", "plan", "content", "evaluation", "exam", "motivation"):
        assert prefs[(category, "push")] is False
    assert not any(channel == "inbox" for _, channel in prefs)  # the inbox is on: the default, so no override row
    assert ("progress", "push") not in prefs  # the weekly summary is never pushed and keeps its email
    assert not offer_due(PLANNED + timedelta(days=60))


def test_accepting_turns_the_inbox_back_on_for_a_category_the_student_had_hidden():
    from modules.notifications.services import preferences

    preferences.set_preferences(USER, [("content", "inbox", False)])
    digest_service.answer(USER, digest_service.Answer.ACCEPT, now=PLANNED)
    assert ("content", "inbox") not in push_overrides()


def test_stopping_puts_the_push_switches_back_and_stops_the_digest():
    digest_service.answer(USER, digest_service.Answer.ACCEPT, now=PLANNED)
    digest_service.answer(USER, digest_service.Answer.STOP, now=PLANNED + timedelta(days=2))
    assert not row().digest_enabled and push_overrides() == {}


def test_after_accepting_a_tracker_alert_reaches_the_inbox_but_not_the_phone(fake_push):
    digest_service.answer(USER, digest_service.Answer.ACCEPT, now=PLANNED)
    result = notify_service.notify(
        USER,
        "goal_reached",
        context={"studied_minutes": 120, "local_date": "2026-10-06"},
        dedupe_ref={"local_date": "2026-10-06"},
        now=PLANNED,
    )
    assert result.dispatch.outcome == "suppressed" and fake_push.sent == []
    assert Notification.objects.filter(event="goal_reached").exists()


def test_the_timer_alert_still_pushes_on_the_digest(bench, fake_push):
    digest_service.answer(USER, digest_service.Answer.ACCEPT, now=PLANNED)
    from modules.notifications.models import ScheduledJob
    from modules.notifications.scheduling import jobs
    from modules.notifications.tests.timer_bench import FOCUS_END

    timer = bench.start(overtime=True)
    job = ScheduledJob.objects.get(subject_key=str(timer.client_id))
    assert jobs.fire_job(job.id, now=FOCUS_END).delivery == "sent"


# --- the digest itself ---------------------------------------------------------------------------------------------


def on_digest(**changes):
    settings_service.update_settings(USER, changes, now=PLANNED) if changes else None
    digest_service.answer(USER, digest_service.Answer.ACCEPT, now=PLANNED)


def unread(n=2, now=PLANNED):
    for _ in range(n):
        item = uuid.uuid4().hex[:8]
        notify_service.create_notification(
            USER,
            "content_published",
            context={"title": "A paper", "item_id": item},
            dedupe_parts={"item_id": item},
            now=now,
        )


def test_the_digest_goes_out_once_at_the_nudge_time_instead_of_the_thought(fake_push):
    on_digest()
    unread(2)
    assert sweep.run_sweep(now=AT).fired == 1
    (payload,) = pushed(fake_push)
    assert payload["title"] == "Your daily digest" and payload["body"] == "2 updates in your inbox."
    assert payload["url"].startswith("/app/notifications?n=") and payload["category"] == "digest"
    n = Notification.objects.get(event="daily_digest")
    assert (n.dedupe_key, n.priority) == ("digest:2026-10-07", 3)
    assert not Notification.objects.filter(event="daily_nudge").exists()
    assert sweep.run_sweep(now=AT + timedelta(minutes=5)).fired == 0 and len(fake_push.sent) == 1


def test_a_day_with_nothing_to_say_sends_nothing_and_old_digests_do_not_count(fake_push):
    on_digest()
    sweep.run_sweep(now=AT)
    assert fake_push.sent == []
    assert not Notification.objects.filter(event="daily_digest").exists()
    unread(1, now=AT + timedelta(hours=20))
    sweep.run_sweep(now=AT + timedelta(days=1))
    assert len(fake_push.sent) == 1
    for n in Notification.objects.exclude(event="daily_digest"):
        n.read_at = AT
        n.save()
    sweep.run_sweep(now=AT + timedelta(days=2))  # only yesterday's unread digest is left: nothing new
    assert len(fake_push.sent) == 1


def test_the_digest_names_revision_and_the_exam_milestone(fake_push, scheme):
    enrollment = Enrollment.objects.create(
        user_id=USER, scheme=scheme, level=scheme.level, exam_date=TODAY + timedelta(days=7)
    )
    chapter = Chapter.objects.filter(subject__scheme=scheme).first()
    ChapterProgress.objects.create(user_id=USER, enrollment=enrollment, chapter=chapter, next_revision_due=TODAY)
    on_digest()
    sweep.run_sweep(now=AT)
    (payload,) = pushed(fake_push)
    assert payload["body"] == "7 days to your exam. 1 chapter due for revision."
    assert payload["url"].startswith("/app/revision")


def test_the_digest_respects_quiet_hours(fake_push):
    on_digest(quiet_start=time(9, 0), quiet_end=time(11, 0))
    unread(1)
    sweep.run_sweep(now=AT)
    assert fake_push.sent == []
    assert Delivery.objects.get(notification__event="daily_digest").status == DeliveryStatus.QUEUED


def test_the_digest_kill_switch(fake_push, settings):
    on_digest()
    unread(1)
    settings.NOTIFICATIONS_DISABLED_EVENTS = ["daily_digest"]
    sweep.run_sweep(now=AT)
    assert fake_push.sent == [] and not Notification.objects.filter(event="daily_digest").exists()


# --- the endpoint --------------------------------------------------------------------------------------------------


def test_get_and_post_digest(auth_client, clock):
    clock.set(PLANNED)
    ignored_run()
    r = auth_client.get(URL)
    assert r.status_code == 200 and r.json() == {"offer": True, "enabled": False, "time": "10:00"}
    r = auth_client.post(URL, {"answer": "seen"}, content_type="application/json")
    assert r.json() == {"offer": False, "enabled": False, "time": "10:00"}
    r = auth_client.post(URL, {"answer": "accept"}, content_type="application/json")
    assert r.status_code == 200 and r.json()["enabled"] is True
    assert auth_client.get("/api/v1/notifications/settings/").json()["digest_enabled"] is True
    r = auth_client.post(URL, {"answer": "stop"}, content_type="application/json")
    assert r.json()["enabled"] is False


def test_get_never_writes(auth_client):
    ignored_run()
    assert auth_client.get(URL).status_code == 200
    assert not NotificationSettings.objects.exists()


def test_an_unknown_answer_is_a_400(auth_client):
    r = auth_client.post(URL, {"answer": "maybe"}, content_type="application/json")
    assert r.status_code == 400


def test_the_endpoint_needs_sign_in(client):
    assert client.get(URL).status_code in (401, 403)


def test_the_endpoint_needs_the_ui_flag(auth_client, monkeypatch):
    monkeypatch.setattr("modules.notifications.flags.flag_enabled", lambda *a, **k: False)
    assert auth_client.get(URL).status_code == 403


def test_export_and_erase_cover_the_digest_fields():
    from modules.notifications.selectors.export import export_all
    from modules.notifications.services.erasure import delete_all_for_user

    digest_service.answer(USER, digest_service.Answer.ACCEPT, now=PLANNED)
    assert export_all(USER)["settings"]["digest_enabled"] is True
    delete_all_for_user(USER)
    assert not NotificationSettings.objects.filter(user_id=USER).exists()
