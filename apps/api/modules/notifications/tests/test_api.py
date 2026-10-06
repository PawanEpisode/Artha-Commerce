import uuid
from datetime import time

import pytest

from modules.notifications.models import NotificationSettings, Preference

pytestmark = pytest.mark.django_db
BASE = "/api/v1/notifications"
USER = uuid.UUID("3f2b8c7e-6d2e-4f0e-9a45-0f9e5b3e1c11")


def put(client, path, body):
    return client.put(f"{BASE}/{path}", body, content_type="application/json")


def post(client, path, body):
    return client.post(f"{BASE}/{path}", body, content_type="application/json")


def test_requires_sign_in(client):
    assert client.get(f"{BASE}/settings/").status_code in (401, 403)


def test_get_settings_returns_defaults_without_writing(auth_client):
    r = auth_client.get(f"{BASE}/settings/")
    assert r.status_code == 200
    body = r.json()
    assert body["timezone"] == "Asia/Kolkata" and body["quiet_start"] == "22:00" and body["nudge_time"] == "10:00"
    assert body["permission_state"] == "not_asked" and body["permission_decided"] is False
    assert not NotificationSettings.objects.exists()


def test_put_settings_partial_update_and_next_nudge(auth_client):
    r = put(auth_client, "settings/", {"timezone": "Asia/Kolkata", "nudge_time": "09:30", "nudge_tone": "driven"})
    assert r.status_code == 200 and r.json()["nudge_time"] == "09:30" and r.json()["nudge_tone"] == "driven"
    row = NotificationSettings.objects.get(user_id=USER)
    assert row.next_nudge_at is not None
    assert put(auth_client, "settings/", {"nudge_enabled": False}).status_code == 200
    row.refresh_from_db()
    assert row.next_nudge_at is None and row.nudge_time == time(9, 30)


@pytest.mark.parametrize(
    "body, field",
    [
        ({"timezone": "Mars/Base"}, "timezone"),
        ({"quiet_start": "22:00", "quiet_end": "22:00"}, "quiet_end"),
        ({"nudge_tone": "angry"}, "nudge_tone"),
        ({"nudge_time": "25:99"}, "nudge_time"),
        ({"bogus": True}, "bogus"),
    ],
)
def test_put_settings_rejects_bad_input_and_writes_nothing(auth_client, body, field):
    r = put(auth_client, "settings/", body)
    assert r.status_code == 400
    assert field in r.json()["error"]["details"]
    assert not NotificationSettings.objects.exists()


def test_categories_merge_defaults_and_overrides(auth_client):
    cats = {c["key"]: c for c in auth_client.get(f"{BASE}/categories/").json()["categories"]}
    assert cats["timer"]["channels"] == {"push": True, "email": False, "inbox": True}
    assert cats["progress"]["channels"] == {"push": False, "email": True, "inbox": True}


def test_preferences_store_only_changes_from_the_default(auth_client):
    r = put(auth_client, "preferences/", {"preferences": [{"category": "timer", "channel": "push", "enabled": False}]})
    assert r.status_code == 200
    assert {c["key"]: c for c in r.json()["categories"]}["timer"]["channels"]["push"] is False
    assert Preference.objects.filter(user_id=USER).count() == 1
    put(auth_client, "preferences/", {"preferences": [{"category": "timer", "channel": "push", "enabled": True}]})
    assert not Preference.objects.exists()


def test_preferences_are_all_or_nothing(auth_client):
    r = put(
        auth_client,
        "preferences/",
        {
            "preferences": [
                {"category": "timer", "channel": "push", "enabled": False},
                {"category": "x", "channel": "push", "enabled": True},
            ]
        },
    )
    assert r.status_code == 400
    assert not Preference.objects.exists()


def test_preferences_reject_unknown_channel_and_empty(auth_client):
    assert (
        put(
            auth_client, "preferences/", {"preferences": [{"category": "timer", "channel": "sms", "enabled": True}]}
        ).status_code
        == 400
    )
    assert put(auth_client, "preferences/", {"preferences": []}).status_code == 400


def test_permission_state_counts_asks_and_records_decision(auth_client):
    r = post(auth_client, "permission-state/", {"state": "pre_prompt_shown", "source": "onboarding"})
    assert r.status_code == 200 and r.json()["permission_ask_count"] == 1 and r.json()["permission_decided"] is False
    post(
        auth_client, "permission-state/", {"state": "pre_prompt_shown", "source": "onboarding"}
    )  # repeat: no extra ask
    assert NotificationSettings.objects.get(user_id=USER).permission_ask_count == 1
    r = post(auth_client, "permission-state/", {"state": "granted", "source": "onboarding"})
    assert r.json()["permission_decided"] is True and r.json()["permission_state"] == "granted"


def test_permission_asks_are_capped_at_three(auth_client):
    for _ in range(5):
        post(auth_client, "permission-state/", {"state": "dismissed", "source": "followup"})
        post(auth_client, "permission-state/", {"state": "pre_prompt_shown", "source": "followup"})
    assert NotificationSettings.objects.get(user_id=USER).permission_ask_count == 3


def test_permission_state_rejects_unknown(auth_client):
    assert post(auth_client, "permission-state/", {"state": "maybe", "source": "settings"}).status_code == 400
    assert post(auth_client, "permission-state/", {"state": "granted", "source": "mars"}).status_code == 400


def test_kill_switch_env_off_returns_notifications_disabled(auth_client, settings):
    settings.NOTIFICATIONS_ENABLED = False
    r = auth_client.get(f"{BASE}/settings/")
    assert r.status_code == 403 and r.json()["error"]["code"] == "notifications_disabled"


def test_flag_off_returns_notifications_disabled(auth_client, monkeypatch):
    monkeypatch.setattr("modules.notifications.flags.flag_enabled", lambda *a, **k: False)
    assert auth_client.get(f"{BASE}/categories/").status_code == 403


def test_students_cannot_see_each_others_settings(auth_client, client, make_token):
    put(auth_client, "settings/", {"nudge_tone": "driven"})
    other = make_token(sub=str(uuid.uuid4()))
    client.defaults["HTTP_AUTHORIZATION"] = f"Bearer {other}"
    assert client.get(f"{BASE}/settings/").json()["nudge_tone"] == "calm"
