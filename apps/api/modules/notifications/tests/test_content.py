"""
New study material (X-01.1 W3.4, `content_published`): the module that owns the content announces it on the event bus;
the listener reaches the students on that level or course once each, through deferred jobs, behind every usual guard.
"""

import json
import logging
import uuid
from datetime import UTC, datetime, timedelta

import pytest

from core import events
from core.events import CONTENT_PUBLISHED
from modules.coverage.models import Enrollment
from modules.notifications.models import Delivery, Notification, Preference, ScheduledJob
from modules.notifications.scheduling import jobs
from modules.notifications.services import content as content_service
from modules.notifications.tests.helpers import register
from modules.notifications.tests.motivation_helpers import OTHER, THIRD, USER

pytestmark = pytest.mark.django_db
NOW = datetime(2026, 10, 7, 4, 30, tzinfo=UTC)


@pytest.fixture(autouse=True)
def devices():
    for user in (USER, OTHER, THIRD):
        register(user, platform="android", browser="chrome")


def enroll(scheme, user):
    return Enrollment.objects.create(user_id=user, scheme=scheme, level=scheme.level)


def publish(scheme, **overrides):
    payload = {"item_id": "amend-2027", "title": "May 2027 amendments", "level_id": scheme.level_id, **overrides}
    events.emit(CONTENT_PUBLISHED, **payload)


def pushed(fake_push):
    return [json.loads(message.body) for _, message in fake_push.sent]


def fire_all():
    for job in ScheduledJob.objects.filter(kind="deliver_deferred", status="pending"):
        jobs.fire_job(job.id, now=job.fire_at)


def test_every_student_on_the_level_gets_one_notification_and_a_job_outside_the_publishers_request(scheme):
    enroll(scheme, USER)
    enroll(scheme, OTHER)
    publish(scheme)
    rows = Notification.objects.filter(event="content_published")
    assert sorted(rows.values_list("user_id", flat=True)) == sorted([USER, OTHER])
    n = rows.get(user_id=USER)
    assert (n.category, n.priority, n.dedupe_key, n.deep_link) == ("content", 3, "content:amend-2027", "/app")
    assert n.title == "New for your course" and n.body == "May 2027 amendments is now available."
    assert ScheduledJob.objects.filter(kind="deliver_deferred").count() == 2 and not Delivery.objects.exists()


def test_the_push_goes_out_when_the_job_fires(scheme, fake_push, clock):
    # `clock` is noon in India: without it the test followed the real time of day and failed inside quiet hours (22:00 to 08:00 IST).
    enroll(scheme, USER)
    publish(scheme, link="/app/syllabus")
    fire_all()
    (payload,) = pushed(fake_push)
    assert payload["title"] == "New for your course" and payload["url"].split("?")[0] == "/app/syllabus"


def test_students_on_other_levels_and_with_archived_enrolments_are_not_told(scheme):
    from modules.syllabus.models import Level

    enroll(scheme, USER)
    other_level = Level.objects.get(course=scheme.level.course, code="final")
    other_scheme = type(scheme).objects.create(level=other_level, code="2023", name="x", status="published")
    Enrollment.objects.create(user_id=OTHER, scheme=other_scheme, level=other_level)
    Enrollment.objects.create(user_id=THIRD, scheme=scheme, level=scheme.level, status="archived")
    publish(scheme)
    assert list(Notification.objects.values_list("user_id", flat=True)) == [USER]


def test_a_whole_course_reaches_every_level_of_it(scheme):
    from modules.syllabus.models import Level

    enroll(scheme, USER)
    other_level = Level.objects.get(course=scheme.level.course, code="final")
    other_scheme = type(scheme).objects.create(level=other_level, code="2023", name="x", status="published")
    Enrollment.objects.create(user_id=OTHER, scheme=other_scheme, level=other_level)
    events.emit(CONTENT_PUBLISHED, item_id="ca-news", title="New ICAI circular", course_id=scheme.level.course_id)
    assert sorted(Notification.objects.values_list("user_id", flat=True)) == sorted([USER, OTHER])


def test_announcing_twice_notifies_each_student_once(scheme):
    enroll(scheme, USER)
    publish(scheme)
    publish(scheme)
    assert Notification.objects.count() == 1 and ScheduledJob.objects.count() == 1


def test_a_different_item_is_a_different_notification(scheme):
    enroll(scheme, USER)
    publish(scheme)
    publish(scheme, item_id="mock-3", title="Mock test 3")
    assert Notification.objects.count() == 2


def test_a_student_who_turned_new_content_off_for_push_gets_it_in_the_inbox_only(scheme, fake_push):
    enroll(scheme, USER)
    Preference.objects.create(user_id=USER, category="content", channel="push", enabled=False)
    publish(scheme)
    fire_all()
    assert pushed(fake_push) == [] and Notification.objects.count() == 1
    assert Delivery.objects.get().suppress_reason == "preference"


def test_an_announcement_with_nobody_to_tell_or_missing_pieces_does_nothing(scheme, caplog):
    enroll(scheme, USER)
    with caplog.at_level(logging.WARNING):
        events.emit(CONTENT_PUBLISHED, item_id="x", title="No audience named")
        events.emit(CONTENT_PUBLISHED, item_id="", title="No id", level_id=scheme.level_id)
        events.emit(CONTENT_PUBLISHED, item_id="x", title="  ", level_id=scheme.level_id)
    assert not Notification.objects.exists()
    assert sum("content_announcement_ignored" in r.getMessage() for r in caplog.records) == 3


@pytest.mark.parametrize("link", ["https://evil.example/x", "//evil.example", "/admin", "/app/../admin"])
def test_a_link_off_the_allow_list_stops_the_announcement(scheme, link):
    enroll(scheme, USER)
    publish(scheme, link=link)
    assert not Notification.objects.exists()


def test_the_switches_stop_it_before_anything_is_written(scheme, settings, monkeypatch):
    enroll(scheme, USER)
    settings.NOTIFICATIONS_DISABLED_EVENTS = frozenset({"content_published"})
    publish(scheme)
    assert not Notification.objects.exists()
    settings.NOTIFICATIONS_DISABLED_EVENTS = frozenset()
    settings.NOTIFICATIONS_ENABLED = False
    publish(scheme)
    assert not Notification.objects.exists()
    settings.NOTIFICATIONS_ENABLED = True
    monkeypatch.setattr("modules.notifications.flags.flag_enabled", lambda *a, **k: False)
    publish(scheme)
    assert not Notification.objects.exists()


def test_a_long_title_is_cut_and_the_body_still_fits(scheme):
    enroll(scheme, USER)
    publish(scheme, title="T" * 500)
    n = Notification.objects.get()
    assert len(n.body) <= 100 and n.body.endswith("…")


def test_one_students_failure_does_not_stop_the_others(scheme, monkeypatch, caplog):
    enroll(scheme, USER)
    enroll(scheme, OTHER)
    real = content_service.notify_service.create_notification

    def flaky(user_id, *args, **kwargs):
        if user_id == min(USER, OTHER):
            raise RuntimeError("boom")
        return real(user_id, *args, **kwargs)

    monkeypatch.setattr(content_service.notify_service, "create_notification", flaky)
    result = content_service.announce(item_id="x", title="Hello", level_id=scheme.level_id, now=NOW)
    assert (result.notified, result.failed) == (1, 1)
    assert any("content_notify_failed" in r.getMessage() and "RuntimeError" in r.getMessage() for r in caplog.records)
    assert "boom" not in caplog.text


def test_the_audience_is_read_in_pages_and_capped_with_a_logged_error(scheme, monkeypatch, caplog):
    users = sorted(uuid.uuid4() for _ in range(7))
    for user in users:
        register(user, platform="android", browser="chrome")
        enroll(scheme, user)
    monkeypatch.setattr(content_service, "PAGE", 3)
    monkeypatch.setattr(content_service, "MAX_AUDIENCE", 5)
    with caplog.at_level(logging.ERROR):
        result = content_service.announce(item_id="big", title="Big release", level_id=scheme.level_id, now=NOW)
    assert (result.notified, result.truncated) == (5, True)
    assert any("content_audience_truncated" in r.getMessage() for r in caplog.records)
    # Announcing again picks up the rest: the five who have it are skipped by their dedupe key.
    monkeypatch.setattr(content_service, "MAX_AUDIENCE", 100)
    again = content_service.announce(item_id="big", title="Big release", level_id=scheme.level_id, now=NOW)
    assert (again.notified, again.skipped, again.truncated) == (2, 5, False)
    assert Notification.objects.filter(event="content_published").count() == 7


def test_the_deferred_job_is_a_moment_ahead_of_the_announcement(scheme):
    enroll(scheme, USER)
    content_service.announce(item_id="x", title="Hello", level_id=scheme.level_id, now=NOW)
    assert ScheduledJob.objects.get().fire_at == NOW + timedelta(seconds=2)
