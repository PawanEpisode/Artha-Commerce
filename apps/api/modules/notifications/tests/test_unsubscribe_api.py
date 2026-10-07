"""The public unsubscribe endpoint: a signed link, no login, safe to repeat, honoured even when sending is off."""

import uuid

import pytest
from django.conf import settings as django_settings

from modules.notifications.domain.unsubscribe import make_token
from modules.notifications.models import Preference
from modules.notifications.services.email_delivery import unsubscribe_token

pytestmark = pytest.mark.django_db
URL = "/api/v1/notifications/unsubscribe/"
USER = uuid.UUID("3f2b8c7e-6d2e-4f0e-9a45-0f9e5b3e1c11")


def switch_exists(enabled=False):
    return Preference.objects.filter(user_id=USER, category="progress", channel="email", enabled=enabled).exists()


def test_a_valid_link_switches_the_email_off_without_a_login(client):
    token = unsubscribe_token(USER, "progress")
    res = client.post(URL, {"token": token}, content_type="application/json")
    assert res.status_code == 200
    assert res.json() == {"category": "progress", "label": "Weekly summary", "unsubscribed": True}
    assert switch_exists()


def test_it_is_safe_to_repeat(client):
    token = unsubscribe_token(USER, "progress")
    for _ in range(2):
        assert client.post(URL, {"token": token}, content_type="application/json").status_code == 200
    assert Preference.objects.filter(user_id=USER, category="progress", channel="email").count() == 1


def test_a_mail_client_one_click_post_works(client):
    token = unsubscribe_token(USER, "progress")
    res = client.post(f"{URL}?t={token}", {"List-Unsubscribe": "One-Click"})  # form encoded, as RFC 8058 says
    assert res.status_code == 200 and switch_exists()


def test_get_only_describes_the_link(client):
    token = unsubscribe_token(USER, "progress")
    res = client.get(f"{URL}?t={token}")
    assert res.status_code == 200 and res.json()["unsubscribed"] is False and res.json()["label"] == "Weekly summary"
    assert not Preference.objects.exists()


@pytest.mark.parametrize(
    "token",
    [
        "",
        "garbage",
        make_token("another-secret", user_id=str(USER), category="progress"),
        make_token(django_settings.SECRET_KEY, user_id="not-a-uuid", category="progress"),
        make_token(django_settings.SECRET_KEY, user_id=str(USER), category="nonsense"),
        make_token(django_settings.SECRET_KEY, user_id=str(USER), category="system"),
    ],
)
def test_anything_but_a_link_we_signed_is_refused_and_changes_nothing(client, token):
    for res in (client.get(f"{URL}?t={token}"), client.post(URL, {"token": token}, content_type="application/json")):
        assert res.status_code == 400 and res.json()["error"]["code"] == "invalid_link"
    assert not Preference.objects.exists()


def test_it_still_works_when_notifications_are_switched_off(client, settings):
    settings.NOTIFICATIONS_ENABLED = False
    token = unsubscribe_token(USER, "progress")
    assert client.post(URL, {"token": token}, content_type="application/json").status_code == 200
    assert switch_exists()


def test_it_is_throttled(client):
    statuses = [client.post(URL, {"token": "x"}, content_type="application/json").status_code for _ in range(25)]
    assert statuses[-1] == 429
