import json
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from rest_framework.exceptions import NotFound

from modules.notifications.domain.catalogue import UnknownEvent
from modules.notifications.domain.copy import Copy
from modules.notifications.errors import InvalidDeepLink, NotificationsDisabled
from modules.notifications.models import Delivery, Notification, Preference
from modules.notifications.services import devices
from modules.notifications.services.notify import create_notification, notify, send_test_push
from modules.notifications.tests.helpers import register

pytestmark = pytest.mark.django_db
USER, OTHER = uuid.uuid4(), uuid.uuid4()
NOW = datetime(2026, 10, 5, 4, 30, tzinfo=UTC)
NIGHT = datetime(2026, 10, 5, 18, 0, tzinfo=UTC)
CTX = {"client_id": "abc", "minutes": 25, "round_number": 2, "subject_name": "GST", "break_minutes": 5}
REF = {"client_id": "abc", "version": 4}


def test_create_builds_copy_link_expiry_and_priority_from_the_catalogue():
    n, created = create_notification(USER, "timer_end", context=CTX, dedupe_parts=REF, now=NOW)
    assert created
    assert (n.event, n.category, n.priority, n.dedupe_key) == ("timer_end", "timer", 0, "timer_end:abc:4")
    assert n.title == "Round 2 done" and "25 minutes on GST" in n.body and n.tag == "timer:abc"
    assert n.deep_link == "/app/focus" and n.expires_at is None and n.context == CTX and n.user_id == USER


def test_create_is_idempotent_on_the_dedupe_key():
    first, c1 = create_notification(USER, "timer_end", context=CTX, dedupe_parts=REF, now=NOW)
    again, c2 = create_notification(USER, "timer_end", context={**CTX, "minutes": 99}, dedupe_parts=REF, now=NOW)
    assert (c1, c2) == (True, False) and first.id == again.id and Notification.objects.count() == 1
    assert again.context["minutes"] == 25  # the first one wins
    create_notification(USER, "timer_end", context=CTX, dedupe_parts={**REF, "version": 5}, now=NOW)
    create_notification(OTHER, "timer_end", context=CTX, dedupe_parts=REF, now=NOW)  # same key, other student
    assert Notification.objects.count() == 3


def test_expiry_comes_from_the_event_spec(monkeypatch):
    from modules.notifications.domain import copy as copy_module

    monkeypatch.setitem(
        copy_module._BUILDERS, "daily_nudge", lambda ctx: Copy("Hi", "Come study", "/app/focus", "nudge")
    )
    n, _ = create_notification(USER, "daily_nudge", context={}, dedupe_parts={"local_date": "2026-10-05"}, now=NOW)
    assert n.expires_at == NOW + timedelta(hours=6)


def test_unknown_event_and_event_without_copy_are_refused_and_store_nothing():
    with pytest.raises(UnknownEvent):
        create_notification(USER, "nope", context={}, dedupe_parts={}, now=NOW)
    with pytest.raises(UnknownEvent):  # catalogued but no reviewed copy yet
        create_notification(USER, "plan_ready", context={}, dedupe_parts={"local_date": "x"}, now=NOW)
    assert not Notification.objects.exists()


def test_missing_dedupe_part_is_a_value_error():
    with pytest.raises(ValueError):
        create_notification(USER, "timer_end", context=CTX, dedupe_parts={"client_id": "abc"}, now=NOW)


@pytest.mark.parametrize("link", ["//evil.example/x", "https://evil.example", "/admin", "/app/../admin"])
def test_a_deep_link_off_the_allow_list_is_rejected_at_creation(monkeypatch, link):
    from modules.notifications.domain import copy as copy_module

    monkeypatch.setitem(copy_module._BUILDERS, "timer_end", lambda ctx: Copy("t", "b", link, "x"))
    with pytest.raises(InvalidDeepLink) as caught:
        create_notification(USER, "timer_end", context=CTX, dedupe_parts=REF, now=NOW)
    assert caught.value.default_code == "invalid_deep_link" and not Notification.objects.exists()


def test_notify_creates_then_sends(fake_push):
    device = register(USER, now=NOW).device
    result = notify(USER, "timer_end", context=CTX, dedupe_ref=REF, now=NOW, intended_at=NOW - timedelta(seconds=1))
    assert result.created and result.dispatch.outcome == "sent"
    assert fake_push.endpoints == [device.endpoint_enc]
    assert json.loads(fake_push.sent[0][1].body)["id"] == str(result.notification.id)
    assert Delivery.objects.get().lateness_ms == 1000


def test_notify_twice_with_the_same_reference_sends_once(fake_push):
    register(USER, now=NOW)
    first = notify(USER, "timer_end", context=CTX, dedupe_ref=REF, now=NOW)
    second = notify(USER, "timer_end", context=CTX, dedupe_ref=REF, now=NOW + timedelta(seconds=3))
    assert (first.created, second.created) == (True, False) and first.notification.id == second.notification.id
    assert second.dispatch.outcome == "already_sent" and len(fake_push.sent) == 1
    assert Notification.objects.count() == 1 and Delivery.objects.count() == 1


def test_notify_accepts_a_single_value_reference_for_single_part_templates(monkeypatch, fake_push):
    from modules.notifications.domain import copy as copy_module

    monkeypatch.setitem(
        copy_module._BUILDERS, "evaluation_ready", lambda ctx: Copy("Ready", "Open it", "/app/focus", "e")
    )
    result = notify(USER, "evaluation_ready", context={}, dedupe_ref="attempt-9", now=NOW)
    assert result.notification.dedupe_key == "evaluation:attempt-9"
    assert result.dispatch.reason.value == "no_device"  # created and judged even with nobody to reach


def test_notify_respects_the_sending_switch_and_the_event_kill_switch(fake_push, monkeypatch, settings):
    register(USER, now=NOW)
    monkeypatch.setattr("modules.notifications.flags.sending_enabled", lambda user_id: False)
    off = notify(USER, "timer_end", context=CTX, dedupe_ref=REF, now=NOW)
    assert off.dispatch.reason.value == "flag_off" and fake_push.sent == []
    assert Delivery.objects.get().suppress_reason == "flag_off" and off.notification.id  # still in the inbox
    monkeypatch.undo()
    settings.NOTIFICATIONS_DISABLED_EVENTS = frozenset({"break_over"})
    killed = notify(
        USER, "break_over", context={"client_id": "abc"}, dedupe_ref={"client_id": "abc", "version": 1}, now=NOW
    )
    assert killed.dispatch.reason.value == "flag_off"


def test_notify_applies_preferences(fake_push):
    register(USER, now=NOW)
    Preference.objects.create(user_id=USER, category="timer", channel="push", enabled=False)
    assert notify(USER, "timer_end", context=CTX, dedupe_ref=REF, now=NOW).dispatch.reason.value == "preference"


# --- the test push ---------------------------------------------------------------------------------------------


def test_test_push_goes_only_to_the_chosen_device_and_each_call_is_a_new_notification(fake_push):
    target = register(USER, now=NOW).device
    register(USER, now=NOW)
    first = send_test_push(USER, target.id, now=NOW)
    second = send_test_push(USER, target.id, now=NOW)
    assert (first.outcome, second.outcome) == ("sent", "sent")
    assert fake_push.endpoints == [target.endpoint_enc] * 2
    notes = Notification.objects.filter(event="test_push")
    assert notes.count() == 2 and len({n.dedupe_key for n in notes}) == 2
    payload = json.loads(fake_push.sent[0][1].body)
    assert payload["title"] == "Test notification" and payload["category"] == "system"
    assert payload["url"].startswith("/app/settings/notifications?n=")
    assert all(not d.counts_toward_cap for d in Delivery.objects.all())


def test_test_push_ignores_quiet_hours_and_the_cap_and_category_switches(fake_push):
    from modules.notifications.models import Delivery as D

    target = register(USER, now=NIGHT).device
    for _ in range(5):
        n, _ = create_notification(
            OTHER, "timer_end", context=CTX, dedupe_parts={**REF, "version": uuid.uuid4().hex}, now=NOW
        )
        D.objects.create(
            notification=n,
            user_id=USER,
            device=target,
            channel="push",
            status="sent",
            counts_toward_cap=True,
            attempted_at=NIGHT,
        )
    for category in ("timer", "tracker", "motivation"):
        Preference.objects.create(user_id=USER, category=category, channel="push", enabled=False)
    assert send_test_push(USER, target.id, now=NIGHT).outcome == "sent"


def test_test_push_still_obeys_the_master_switch_and_reports_why(fake_push):
    from modules.notifications.models import NotificationSettings

    target = register(USER, now=NOW).device
    NotificationSettings.objects.create(user_id=USER, push_master=False)
    result = send_test_push(USER, target.id, now=NOW)
    assert (result.outcome, result.reason.value) == ("suppressed", "preference") and fake_push.sent == []


def test_test_push_obeys_the_sending_switch(fake_push, monkeypatch):
    target = register(USER, now=NOW).device
    monkeypatch.setattr("modules.notifications.flags.sending_enabled", lambda user_id: False)
    with pytest.raises(NotificationsDisabled):
        send_test_push(USER, target.id, now=NOW)
    assert not Notification.objects.exists() and fake_push.sent == []


def test_test_push_to_someone_elses_or_a_removed_device_is_a_404(fake_push):
    theirs = register(OTHER, now=NOW).device
    mine = register(USER, now=NOW).device
    devices.remove_device(USER, mine.id)
    for target in (theirs.id, mine.id, uuid.uuid4()):
        with pytest.raises(NotFound):
            send_test_push(USER, target, now=NOW)
    assert fake_push.sent == [] and not Notification.objects.exists()
