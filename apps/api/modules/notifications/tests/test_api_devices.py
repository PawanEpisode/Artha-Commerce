import json
import uuid

import pytest

from core.fields import hmac_hex
from modules.notifications.models import Delivery, Device, Notification
from modules.notifications.tests.helpers import make_endpoint, make_keys, subscription

pytestmark = pytest.mark.django_db
BASE = "/api/v1/notifications"
USER = uuid.UUID("3f2b8c7e-6d2e-4f0e-9a45-0f9e5b3e1c11")
OTHER = uuid.UUID("9d1c2b3a-0000-4000-8000-000000000002")


def post(client, path, body=None):
    return client.post(f"{BASE}/{path}", body or {}, content_type="application/json")


def register_body(sub=None, **extra):
    return {
        "subscription": sub or subscription(),
        "platform": "android",
        "browser": "chrome",
        "display_mode": "browser",
        **extra,
    }


def register(client, sub=None, **extra):
    return post(client, "devices/", register_body(sub, **extra))


def test_requires_sign_in(client):
    assert client.get(f"{BASE}/devices/").status_code in (401, 403)
    assert client.post(f"{BASE}/devices/", {}, content_type="application/json").status_code in (401, 403)


def test_register_returns_the_device_id_only(auth_client):
    sub = subscription()
    r = register(auth_client, sub, sw_version="v3")
    assert r.status_code == 201 and set(r.json()) == {"device_id"}
    row = Device.objects.get()
    assert (
        r.json()["device_id"] == str(row.id) and row.user_id == USER and row.endpoint_hash == hmac_hex(sub["endpoint"])
    )
    assert (row.label, row.platform, row.browser, row.sw_version) == ("Chrome on Android", "android", "chrome", "v3")


def test_register_accepts_the_spike_subscription_shape_with_a_client_label_and_expiration(auth_client):
    sub = {**subscription(), "expirationTime": None}
    r = register(auth_client, sub, label="<script>alert(1)</script>")
    assert r.status_code == 201
    assert Device.objects.get().label == "Chrome on Android"  # the label is derived, never taken from the client


def test_registering_twice_leaves_one_row_and_answers_200_with_the_same_id(auth_client):
    sub = subscription()
    first, second = register(auth_client, sub), register(auth_client, sub)
    assert (first.status_code, second.status_code) == (201, 200)
    assert first.json() == second.json() and Device.objects.count() == 1


def test_defaults_for_optional_fields(auth_client):
    assert post(auth_client, "devices/", {"subscription": subscription()}).status_code == 201
    row = Device.objects.get()
    assert (row.platform, row.browser, row.display_mode, row.label) == ("other", "other", "browser", "Browser")


@pytest.mark.parametrize(
    "endpoint",
    [
        "http://fcm.googleapis.com/x",
        "https://evil.example/x",
        "https://fcm.googleapis.com@evil.example/x",
        "https://127.0.0.1/x",
    ],
)
def test_endpoint_off_the_allow_list_is_invalid_endpoint(auth_client, endpoint):
    r = register(auth_client, {"endpoint": endpoint, "keys": make_keys()})
    assert r.status_code == 400 and r.json()["error"]["code"] == "invalid_endpoint"
    assert not Device.objects.exists()


def test_bad_keys_are_invalid_endpoint_and_bad_shape_is_a_400(auth_client):
    r = register(auth_client, {"endpoint": make_endpoint(), "keys": {"p256dh": "x", "auth": "y"}})
    assert r.status_code == 400 and r.json()["error"]["code"] == "invalid_endpoint"
    for body in (
        {},
        {"subscription": {"endpoint": make_endpoint()}},
        register_body(platform="palm"),
        register_body(sw_version="x" * 17),
    ):
        assert post(auth_client, "devices/", body).status_code == 400
    assert not Device.objects.exists()


def test_the_eleventh_device_is_a_409_device_limit(auth_client):
    for _ in range(10):
        assert register(auth_client).status_code == 201
    r = register(auth_client)
    assert r.status_code == 409 and r.json()["error"]["code"] == "device_limit"
    assert Device.objects.count() == 10


def test_list_shows_label_platform_browser_mode_and_last_seen_without_secrets(auth_client):
    sub = subscription()
    register(auth_client, sub, display_mode="standalone", platform="ios", browser="safari")
    Device.objects.create(
        user_id=OTHER,
        kind="web_push",
        endpoint_enc="https://fcm.googleapis.com/o",
        endpoint_hash="h",
        p256dh_enc="p",
        auth_enc="a",
    )
    r = auth_client.get(f"{BASE}/devices/")
    assert r.status_code == 200
    (d,) = r.json()["devices"]
    assert set(d) == {"id", "label", "platform", "browser", "display_mode", "last_seen_at", "created_at"}
    assert (d["label"], d["platform"], d["browser"], d["display_mode"]) == (
        "Safari on iOS (installed app)",
        "ios",
        "safari",
        "standalone",
    )
    text = json.dumps(r.json())
    assert sub["endpoint"] not in text and sub["keys"]["auth"] not in text and sub["keys"]["p256dh"] not in text


def test_no_response_ever_contains_a_secret(auth_client, fake_push):
    sub = subscription()
    responses = [register(auth_client, sub), register(auth_client, sub), auth_client.get(f"{BASE}/devices/")]
    device_id = responses[0].json()["device_id"]
    responses.append(post(auth_client, f"devices/{device_id}/test/"))
    responses.append(auth_client.delete(f"{BASE}/devices/{device_id}/"))
    responses.append(register(auth_client, {"endpoint": "https://evil.example/zz", "keys": sub["keys"]}))
    for r in responses:
        body = r.content.decode()
        assert sub["endpoint"] not in body and sub["keys"]["auth"] not in body and sub["keys"]["p256dh"] not in body
        assert "evil.example/zz" not in body


def test_delete_removes_own_device_and_is_repeatable(auth_client):
    device_id = register(auth_client).json()["device_id"]
    assert auth_client.delete(f"{BASE}/devices/{device_id}/").status_code == 204
    assert auth_client.get(f"{BASE}/devices/").json()["devices"] == []
    row = Device.objects.get()
    assert row.revoked_reason == "user_removed" and row.revoked_at is not None
    assert auth_client.delete(f"{BASE}/devices/{device_id}/").status_code == 204


def test_delete_of_another_students_or_an_unknown_device_is_404(auth_client):
    theirs = Device.objects.create(
        user_id=OTHER,
        kind="web_push",
        endpoint_enc="https://fcm.googleapis.com/o",
        endpoint_hash="h",
        p256dh_enc="p",
        auth_enc="a",
    )
    for target in (theirs.id, uuid.uuid4()):
        r = auth_client.delete(f"{BASE}/devices/{target}/")
        assert r.status_code == 404 and r.json()["error"]["code"] == "not_found"
    theirs.refresh_from_db()
    assert theirs.revoked_at is None


def test_removing_then_registering_again_reuses_the_row(auth_client):
    sub = subscription()
    first = register(auth_client, sub).json()["device_id"]
    auth_client.delete(f"{BASE}/devices/{first}/")
    again = register(auth_client, sub)
    assert again.json()["device_id"] == first and Device.objects.count() == 1
    assert len(auth_client.get(f"{BASE}/devices/").json()["devices"]) == 1


def test_test_push_sends_a_real_notification_to_that_device(auth_client, fake_push):
    sub = subscription()
    device_id = register(auth_client, sub).json()["device_id"]
    r = post(auth_client, f"devices/{device_id}/test/")
    assert r.status_code == 200 and r.json() == {"result": "sent", "reason": None}
    assert fake_push.endpoints == [sub["endpoint"]]
    assert Notification.objects.filter(event="test_push", user_id=USER).count() == 1
    assert Delivery.objects.get().status == "sent"


def test_test_push_reports_a_suppression_reason(auth_client, fake_push):
    device_id = register(auth_client).json()["device_id"]
    put = auth_client.put(f"{BASE}/settings/", {"push_master": False}, content_type="application/json")
    assert put.status_code == 200
    assert post(auth_client, f"devices/{device_id}/test/").json() == {"result": "suppressed", "reason": "preference"}
    assert fake_push.sent == []


def test_test_push_reports_a_failed_send(auth_client, fake_push):
    from modules.notifications.channels import SendResult

    device_id = register(auth_client).json()["device_id"]
    fake_push.script(SendResult.failed("timeout"))
    assert post(auth_client, f"devices/{device_id}/test/").json() == {"result": "failed", "reason": None}


def test_test_push_for_another_students_device_is_404(auth_client, fake_push):
    theirs = Device.objects.create(
        user_id=OTHER,
        kind="web_push",
        endpoint_enc="https://fcm.googleapis.com/o",
        endpoint_hash="h",
        p256dh_enc="p",
        auth_enc="a",
    )
    assert post(auth_client, f"devices/{theirs.id}/test/").status_code == 404
    assert fake_push.sent == []


def test_test_push_is_403_when_sending_is_off_even_though_the_ui_is_on(auth_client, fake_push, monkeypatch):
    device_id = register(auth_client).json()["device_id"]
    monkeypatch.setattr("modules.notifications.flags.sending_enabled", lambda user_id: False)
    r = post(auth_client, f"devices/{device_id}/test/")
    assert r.status_code == 403 and r.json()["error"]["code"] == "notifications_disabled"
    assert fake_push.sent == []


def test_sixth_test_push_in_a_minute_is_429(auth_client, fake_push):
    device_id = register(auth_client).json()["device_id"]
    codes = [post(auth_client, f"devices/{device_id}/test/").status_code for _ in range(6)]
    assert codes == [200] * 5 + [429]
    assert len(fake_push.sent) == 5


def test_test_budget_is_separate_from_the_write_and_read_budgets(auth_client, fake_push):
    device_id = register(auth_client).json()["device_id"]
    for _ in range(5):
        post(auth_client, f"devices/{device_id}/test/")
    assert post(auth_client, f"devices/{device_id}/test/").status_code == 429
    assert auth_client.get(f"{BASE}/devices/").status_code == 200
    assert register(auth_client).status_code == 201


def test_every_endpoint_is_403_when_notifications_are_off(auth_client, settings):
    settings.NOTIFICATIONS_ENABLED = False
    device = uuid.uuid4()
    for r in (
        auth_client.get(f"{BASE}/devices/"),
        register(auth_client),
        auth_client.delete(f"{BASE}/devices/{device}/"),
        post(auth_client, f"devices/{device}/test/"),
    ):
        assert r.status_code == 403 and r.json()["error"]["code"] == "notifications_disabled"
    assert not Device.objects.exists()


def test_export_lists_devices_without_secrets_and_erasure_removes_everything(auth_client, fake_push):
    from modules.notifications.selectors.export import export_all
    from modules.notifications.services.erasure import delete_all_for_user

    sub = subscription()
    device_id = register(auth_client, sub).json()["device_id"]
    post(auth_client, f"devices/{device_id}/test/")
    text = json.dumps(export_all(USER), default=str)
    assert sub["endpoint"] not in text and sub["keys"]["auth"] not in text and sub["keys"]["p256dh"] not in text
    assert "Chrome on Android" in text
    delete_all_for_user(USER)
    assert not Device.objects.exists() and not Delivery.objects.exists() and not Notification.objects.exists()
