"""POST inbox/{id}/click/: the page opened from a notification reports it."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from modules.notifications.models import Delivery, Notification
from modules.notifications.services import inbox
from modules.notifications.tests.helpers import register

pytestmark = pytest.mark.django_db
BASE = "/api/v1/notifications"
USER = uuid.UUID("3f2b8c7e-6d2e-4f0e-9a45-0f9e5b3e1c11")
OTHER = uuid.uuid4()
NOW = datetime(2026, 10, 5, 4, 30, tzinfo=UTC)


def make(user=USER, *, deliveries=1):
    n = Notification.objects.create(
        user_id=user,
        category="timer",
        event="timer_end",
        dedupe_key=f"timer_end:{uuid.uuid4().hex}",
        title="Round 1 done",
        body="25 minutes.",
        deep_link="/app/focus",
        tag="timer:x",
        priority=0,
    )
    for _ in range(deliveries):
        Delivery.objects.create(
            notification=n,
            user_id=user,
            device=register(user).device,
            channel="push",
            status="sent",
            sent_at=NOW,
            attempted_at=NOW,
        )
    return n


def click(client, notification_id):
    return client.post(f"{BASE}/inbox/{notification_id}/click/", {}, content_type="application/json")


def test_requires_sign_in(client):
    assert click(client, uuid.uuid4()).status_code in (401, 403)


def test_a_click_marks_the_notification_read_and_its_pushes_clicked(auth_client):
    n = make(deliveries=2)
    r = click(auth_client, n.id)
    assert r.status_code == 204 and r.content == b""
    n.refresh_from_db()
    assert n.read_at is not None
    assert all(d.clicked_at is not None for d in Delivery.objects.filter(notification=n))


def test_a_repeat_is_harmless_and_keeps_the_first_timestamps(auth_client):
    n = make()
    assert click(auth_client, n.id).status_code == 204
    n.refresh_from_db()
    first_read, first_click = n.read_at, Delivery.objects.get(notification=n).clicked_at
    assert click(auth_client, n.id).status_code == 204
    n.refresh_from_db()
    assert n.read_at == first_read and Delivery.objects.get(notification=n).clicked_at == first_click


def test_only_pushes_that_were_sent_count_as_clicked(auth_client):
    n = make(deliveries=0)
    Delivery.objects.create(
        notification=n, user_id=USER, channel="push", status="suppressed", suppress_reason="no_device", attempted_at=NOW
    )
    click(auth_client, n.id)
    assert Delivery.objects.get(notification=n).clicked_at is None
    n.refresh_from_db()
    assert n.read_at is not None  # it is still read: the student did open it


def test_another_students_notification_is_a_404_and_stays_untouched(auth_client):
    n = make(OTHER)
    assert click(auth_client, n.id).status_code == 404
    n.refresh_from_db()
    assert n.read_at is None and Delivery.objects.get(notification=n).clicked_at is None


def test_an_unknown_id_is_a_404(auth_client):
    assert click(auth_client, uuid.uuid4()).status_code == 404


def test_a_malformed_id_is_a_404(auth_client):
    assert auth_client.post(f"{BASE}/inbox/not-a-uuid/click/").status_code == 404


def test_the_click_is_behind_the_environment_switch_and_the_ui_flag(auth_client, settings, monkeypatch):
    n = make()
    settings.NOTIFICATIONS_ENABLED = False
    r = click(auth_client, n.id)
    assert r.status_code == 403 and r.json()["error"]["code"] == "notifications_disabled"
    settings.NOTIFICATIONS_ENABLED = True
    monkeypatch.setattr("modules.notifications.flags.flag_enabled", lambda *a, **k: False)
    assert click(auth_client, n.id).status_code == 403
    n.refresh_from_db()
    assert n.read_at is None


def test_it_draws_on_the_write_budget(auth_client, monkeypatch):
    from rest_framework.throttling import ScopedRateThrottle

    monkeypatch.setitem(ScopedRateThrottle.THROTTLE_RATES, "notifications_write", "2/min")
    n = make()
    assert [click(auth_client, n.id).status_code for _ in range(3)] == [204, 204, 429]
    assert auth_client.get(f"{BASE}/settings/").status_code == 200  # reads have their own budget


def test_the_service_stamps_the_time_it_is_given():
    n = make()
    later = NOW + timedelta(minutes=3)
    inbox.mark_clicked(USER, n.id, now=later)
    n.refresh_from_db()
    assert n.read_at == later and Delivery.objects.get(notification=n).clicked_at == later
