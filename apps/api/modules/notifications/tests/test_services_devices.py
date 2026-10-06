import uuid
from datetime import UTC, datetime, timedelta

import pytest
from django.db import IntegrityError, connection
from rest_framework.exceptions import NotFound

from core.fields import hmac_hex
from modules.notifications import selectors
from modules.notifications.domain.enums import RevokeReason
from modules.notifications.errors import DeviceLimit, InvalidEndpoint
from modules.notifications.models import Device
from modules.notifications.services import devices
from modules.notifications.tests.helpers import make_endpoint, make_keys, register

pytestmark = pytest.mark.django_db
USER, OTHER = uuid.uuid4(), uuid.uuid4()
T0 = datetime(2026, 10, 5, 4, 30, tzinfo=UTC)


def test_register_creates_a_row_keyed_by_the_endpoint_hash_with_a_derived_label():
    endpoint = make_endpoint()
    result = register(USER, endpoint, platform="android", browser="chrome", sw_version="v3", now=T0)
    d = result.device
    assert result.created and d.kind == "web_push" and d.endpoint_hash == hmac_hex(endpoint)
    assert (d.label, d.platform, d.browser, d.sw_version, d.last_seen_at) == (
        "Chrome on Android",
        "android",
        "chrome",
        "v3",
        T0,
    )
    assert d.revoked_at is None and d.consecutive_failures == 0


def test_secrets_are_encrypted_at_rest_and_decrypt_on_load():
    endpoint, keys = make_endpoint(), make_keys()
    d = register(USER, endpoint, keys).device
    with connection.cursor() as c:
        c.execute(
            "select endpoint_enc, p256dh_enc, auth_enc, endpoint_hash from notifications_device where id = %s",
            [d.id.hex if connection.vendor == "sqlite" else d.id],
        )
        raw = c.fetchone()
    stored = " ".join(str(v) for v in raw)
    assert endpoint not in stored and keys["p256dh"] not in stored and keys["auth"] not in stored
    assert endpoint.split("/")[-1] not in stored
    loaded = Device.objects.get(id=d.id)
    assert (loaded.endpoint_enc, loaded.p256dh_enc, loaded.auth_enc) == (endpoint, keys["p256dh"], keys["auth"])


def test_registering_twice_leaves_one_row_and_refreshes_it():
    endpoint, keys = make_endpoint(), make_keys()
    first = register(USER, endpoint, keys, now=T0)
    again = register(USER, endpoint, keys, browser="edge", now=T0 + timedelta(hours=1))
    assert first.created and not again.created and first.device.id == again.device.id
    assert Device.objects.count() == 1
    row = Device.objects.get()
    assert row.browser == "edge" and row.label == "Edge" and row.last_seen_at == T0 + timedelta(hours=1)


def test_resubscribing_with_new_keys_for_the_same_endpoint_updates_them():
    endpoint = make_endpoint()
    register(USER, endpoint)
    new_keys = make_keys()
    register(USER, endpoint, new_keys)
    row = Device.objects.get()
    assert (row.p256dh_enc, row.auth_enc) == (new_keys["p256dh"], new_keys["auth"])


def test_a_revoked_row_is_reused_and_comes_back_healthy():
    endpoint, keys = make_endpoint(), make_keys()
    d = register(USER, endpoint, keys, now=T0).device
    Device.objects.filter(id=d.id).update(consecutive_failures=4, first_failure_at=T0)
    devices.remove_device(USER, d.id, now=T0)
    again = register(USER, endpoint, keys, now=T0 + timedelta(days=1))
    assert not again.created and again.device.id == d.id and Device.objects.count() == 1
    row = Device.objects.get()
    assert row.revoked_at is None and row.revoked_reason is None
    assert row.consecutive_failures == 0 and row.first_failure_at is None


def test_ten_active_devices_is_the_limit():
    for _ in range(10):
        register(USER)
    with pytest.raises(DeviceLimit) as caught:
        register(USER)
    assert caught.value.default_code == "device_limit" and caught.value.extra == {"limit": 10}
    assert Device.objects.filter(user_id=USER).count() == 10
    register(OTHER)  # the limit is per student


def test_refreshing_an_existing_device_at_the_limit_is_allowed():
    endpoint, keys = make_endpoint(), make_keys()
    register(USER, endpoint, keys)
    for _ in range(9):
        register(USER)
    assert not register(USER, endpoint, keys).created


def test_reviving_a_revoked_device_counts_against_the_limit_and_removing_frees_a_slot():
    endpoint, keys = make_endpoint(), make_keys()
    old = register(USER, endpoint, keys).device
    devices.remove_device(USER, old.id)
    made = [register(USER).device for _ in range(10)]
    with pytest.raises(DeviceLimit):
        register(USER, endpoint, keys)
    devices.remove_device(USER, made[0].id)
    assert register(USER, endpoint, keys).device.id == old.id


@pytest.mark.parametrize(
    "endpoint",
    [
        "http://fcm.googleapis.com/fcm/send/x",
        "https://evil.example/fcm/send/x",
        "https://fcm.googleapis.com.evil.example/x",
        "https://127.0.0.1/x",
        "https://user@fcm.googleapis.com/x",
        "https://fcm.googleapis.com:8443/x",
        "",
    ],
)
def test_endpoints_off_the_allow_list_are_refused_and_store_nothing(endpoint):
    keys = make_keys()
    with pytest.raises(InvalidEndpoint) as caught:
        devices.register_device(USER, endpoint=endpoint, p256dh=keys["p256dh"], auth=keys["auth"])
    assert caught.value.default_code == "invalid_endpoint"
    assert not Device.objects.exists()


def test_malformed_keys_are_refused():
    with pytest.raises(InvalidEndpoint):
        devices.register_device(USER, endpoint=make_endpoint(), p256dh="nope", auth="nope")
    assert not Device.objects.exists()


def test_same_browser_signing_in_as_another_student_moves_the_device():
    endpoint, keys = make_endpoint(), make_keys()
    first = register(USER, endpoint, keys).device
    moved = register(OTHER, endpoint, keys)
    assert not moved.created and moved.device.id == first.id and Device.objects.count() == 1
    assert Device.objects.get().user_id == OTHER
    assert selectors.list_devices(USER) == [] and len(selectors.list_devices(OTHER)) == 1


def test_a_different_student_cannot_claim_an_endpoint_without_its_keys():
    endpoint = make_endpoint()
    register(USER, endpoint, make_keys())
    with pytest.raises(InvalidEndpoint):
        register(OTHER, endpoint, make_keys())
    assert Device.objects.get().user_id == USER


def test_moving_a_device_to_a_student_at_the_limit_is_refused():
    endpoint, keys = make_endpoint(), make_keys()
    register(USER, endpoint, keys)
    for _ in range(10):
        register(OTHER)
    with pytest.raises(DeviceLimit):
        register(OTHER, endpoint, keys)
    assert Device.objects.get(endpoint_hash=hmac_hex(endpoint)).user_id == USER


def test_a_lost_creation_race_falls_back_to_updating_the_winner(monkeypatch):
    endpoint, keys = make_endpoint(), make_keys()
    winner = register(OTHER, endpoint, keys).device
    real, calls = devices._upsert, []

    def flaky(*args, **kwargs):
        calls.append(1)
        if len(calls) == 1:
            raise IntegrityError("duplicate endpoint_hash")
        return real(*args, **kwargs)

    monkeypatch.setattr(devices, "_upsert", flaky)
    result = register(USER, endpoint, keys)
    assert len(calls) == 2 and result.device.id == winner.id


def test_remove_revokes_softly_with_the_user_removed_reason():
    d = register(USER).device
    devices.remove_device(USER, d.id, now=T0)
    row = Device.objects.get(id=d.id)
    assert row.revoked_at == T0 and row.revoked_reason == RevokeReason.USER_REMOVED
    assert selectors.list_devices(USER) == [] and selectors.active_push_devices(USER) == []


def test_remove_is_repeatable_and_keeps_the_first_timestamp():
    d = register(USER).device
    devices.remove_device(USER, d.id, now=T0)
    devices.remove_device(USER, d.id, now=T0 + timedelta(days=1))
    assert Device.objects.get(id=d.id).revoked_at == T0


def test_removing_another_students_or_an_unknown_device_is_a_404_and_changes_nothing():
    theirs = register(OTHER).device
    for target in (theirs.id, uuid.uuid4()):
        with pytest.raises(NotFound):
            devices.remove_device(USER, target)
    assert Device.objects.get(id=theirs.id).revoked_at is None


def test_touch_last_seen_only_for_own_active_devices():
    d = register(USER, now=T0).device
    assert devices.touch_last_seen(USER, d.id, now=T0 + timedelta(hours=2))
    assert Device.objects.get(id=d.id).last_seen_at == T0 + timedelta(hours=2)
    assert not devices.touch_last_seen(OTHER, d.id) and not devices.touch_last_seen(USER, uuid.uuid4())
    devices.remove_device(USER, d.id)
    assert not devices.touch_last_seen(USER, d.id)


def test_list_devices_has_no_secrets_and_orders_by_last_seen():
    old = register(USER, now=T0, platform="windows", browser="edge").device
    new = register(USER, now=T0 + timedelta(hours=1), platform="android", browser="chrome").device
    register(OTHER)
    rows = selectors.list_devices(USER)
    assert [r["id"] for r in rows] == [new.id, old.id]
    assert set(rows[0]) == {"id", "label", "platform", "browser", "display_mode", "last_seen_at", "created_at"}


def test_get_active_device_is_a_404_for_others_and_removed_devices():
    mine, theirs = register(USER).device, register(OTHER).device
    assert selectors.get_active_device(USER, mine.id).id == mine.id
    with pytest.raises(NotFound):
        selectors.get_active_device(USER, theirs.id)
    devices.remove_device(USER, mine.id)
    with pytest.raises(NotFound):
        selectors.get_active_device(USER, mine.id)


def test_record_success_clears_the_failure_run():
    d = register(USER).device
    devices.record_failure(d.id, now=T0, http_status=503)
    devices.record_success(d.id, now=T0 + timedelta(minutes=1))
    row = Device.objects.get(id=d.id)
    assert (row.consecutive_failures, row.first_failure_at, row.last_success_at) == (0, None, T0 + timedelta(minutes=1))


def test_record_failure_applies_the_health_rule():
    d = register(USER).device
    assert devices.record_failure(d.id, now=T0, http_status=500) is None
    row = Device.objects.get(id=d.id)
    assert (row.consecutive_failures, row.first_failure_at, row.last_failure_at) == (1, T0, T0)
    for hours in (1, 2, 3):
        assert devices.record_failure(d.id, now=T0 + timedelta(hours=hours), http_status=500) is None
    assert devices.record_failure(d.id, now=T0 + timedelta(days=8), http_status=500) is RevokeReason.FAILURES
    row.refresh_from_db()
    assert row.revoked_reason == "failures" and row.revoked_at == T0 + timedelta(days=8)
    assert devices.record_failure(d.id, now=T0 + timedelta(days=9), http_status=410) is None  # already revoked


def test_a_gone_answer_revokes_at_once():
    d = register(USER).device
    assert devices.record_failure(d.id, now=T0, http_status=410) is RevokeReason.GONE
    assert Device.objects.get(id=d.id).revoked_reason == "gone"
