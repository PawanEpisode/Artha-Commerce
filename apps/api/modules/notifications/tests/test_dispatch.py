import json
import logging
import uuid
from datetime import UTC, datetime, timedelta

import pytest

from modules.notifications import dispatch as dispatch_module
from modules.notifications.channels import ChannelNotConfigured, SendResult, Urgency
from modules.notifications.domain.policy import Action
from modules.notifications.models import Delivery, Device, Notification, NotificationSettings, Preference
from modules.notifications.services import devices as device_service
from modules.notifications.tests.helpers import register

pytestmark = pytest.mark.django_db
USER, OTHER = uuid.uuid4(), uuid.uuid4()
NOW = datetime(2026, 10, 5, 4, 30, tzinfo=UTC)  # Monday 10:00 in India
NIGHT = datetime(2026, 10, 5, 18, 0, tzinfo=UTC)  # 23:30 in India: inside the default quiet hours


def make_notification(event="timer_end", *, user=USER, key=None, priority=None, expires_at=None, created_at=None):
    from modules.notifications.domain.catalogue import get_event

    spec = get_event(event)
    n = Notification.objects.create(
        user_id=user,
        category=spec.category.value,
        event=event,
        dedupe_key=key or f"{event}:{uuid.uuid4().hex}",
        title="Round 2 done",
        body="25 minutes on GST.",
        deep_link="/app/focus",
        tag="timer:abc",
        priority=spec.priority if priority is None else priority,
        expires_at=expires_at,
    )
    if created_at:
        Notification.objects.filter(id=n.id).update(created_at=created_at)
        n.refresh_from_db()
    return n


def rows(n=None):
    qs = Delivery.objects.all() if n is None else Delivery.objects.filter(notification=n)
    return list(qs.order_by("attempted_at", "id"))


def log_lines(caplog, name):
    return [r for r in caplog.records if r.getMessage().startswith(name + " ")]


@pytest.fixture
def device():
    return register(USER, platform="android", browser="chrome", sw_version="v7", now=NOW).device


def sent_row(user, event="daily_nudge", at=NOW):
    n = make_notification(event, user=user)
    d = Device.objects.filter(user_id=user).first() or register(user).device
    return Delivery.objects.create(
        notification=n, user_id=user, device=d, channel="push", status="sent", counts_toward_cap=True, attempted_at=at
    )


# --- sending ---------------------------------------------------------------------------------------------------


def test_exempt_event_is_sent_to_every_active_device_with_payload_ttl_and_urgency(fake_push, device, caplog):
    second = register(USER, now=NOW).device
    register(OTHER)  # another student's device is never touched
    n = make_notification("timer_end", created_at=NOW - timedelta(seconds=2))
    caplog.set_level(logging.INFO)
    result = dispatch_module.dispatch(n, now=NOW)
    assert (result.action, result.sent, result.failed, result.outcome) == (Action.SEND, 2, 0, "sent")
    assert len(fake_push.sent) == 2
    secrets, message = fake_push.sent[0]
    payload = json.loads(message.body)
    assert payload["v"] == 1 and payload["id"] == str(n.id) and payload["url"] == f"/app/focus?n={n.id}"
    assert payload["title"] == "Round 2 done" and payload["category"] == "timer" and payload["tag"] == "timer:abc"
    assert (message.ttl_seconds, message.urgency) == (300, Urgency.HIGH)
    assert {s.endpoint for s, _ in fake_push.sent} == {device.endpoint_enc, second.endpoint_enc}
    for row in rows(n):
        assert row.status == "sent" and row.http_status == 201 and row.error_code is None and row.attempt == 1
        assert row.counts_toward_cap is False  # priority 0 never uses the student's budget
        assert row.sent_at == NOW and row.lateness_ms == 2000 and row.channel == "push"
    assert {r.device_id for r in rows(n)} == {device.id, second.id}


def test_sent_push_updates_device_health_and_logs_push_sent_exactly_per_the_prd(device, caplog):
    Device.objects.filter(id=device.id).update(consecutive_failures=3, first_failure_at=NOW - timedelta(days=1))
    caplog.set_level(logging.INFO)
    dispatch_module.dispatch(make_notification("timer_end", created_at=NOW), now=NOW)
    d = Device.objects.get(id=device.id)
    assert (d.consecutive_failures, d.first_failure_at, d.last_success_at) == (0, None, NOW)
    (record,) = log_lines(caplog, "push_sent")
    assert record.push == {
        "event": "timer_end",
        "category": "timer",
        "device_kind": "web_push",
        "status": "sent",
        "http_status": 201,
        "lateness_ms": 0,
        "attempt": 1,
        "sw_version": "v7",
    }


@pytest.mark.parametrize(
    "event, counts", [("break_over", False), ("goal_reached", True), ("revision_due", True), ("daily_nudge", True)]
)
def test_only_priority_one_to_three_sent_pushes_count_toward_the_cap(device, event, counts):
    n = make_notification(event, created_at=NOW)
    dispatch_module.dispatch(n, now=NOW)
    assert rows(n)[0].counts_toward_cap is counts


def test_urgency_and_ttl_follow_priority_and_expiry(fake_push, device):
    n = make_notification("revision_due", expires_at=NOW + timedelta(hours=12))
    dispatch_module.dispatch(n, now=NOW)
    _, message = fake_push.sent[0]
    assert (message.ttl_seconds, message.urgency) == (12 * 3600, Urgency.LOW)


# --- the policy outcomes -----------------------------------------------------------------------------------------


def assert_suppressed(n, reason, caplog, fake_push, event):
    (row,) = rows(n)
    assert row.status == "suppressed" and row.suppress_reason == reason and row.device_id is None
    assert row.channel == "push" and row.counts_toward_cap is False and row.attempted_at is not None
    assert fake_push.sent == []
    (record,) = log_lines(caplog, "push_suppressed")
    assert record.push == {"event": event, "reason": reason}


def test_category_switched_off_suppresses_with_preference(fake_push, device, caplog):
    Preference.objects.create(user_id=USER, category="timer", channel="push", enabled=False)
    caplog.set_level(logging.INFO)
    n = make_notification("timer_end")
    result = dispatch_module.dispatch(n, now=NOW)
    assert (result.action, result.reason.value, result.outcome) == (Action.SUPPRESS, "preference", "suppressed")
    assert_suppressed(n, "preference", caplog, fake_push, "timer_end")


def test_master_switch_off_suppresses_with_preference(fake_push, device, caplog):
    NotificationSettings.objects.create(user_id=USER, push_master=False)
    caplog.set_level(logging.INFO)
    n = make_notification("timer_end")
    dispatch_module.dispatch(n, now=NOW)
    assert_suppressed(n, "preference", caplog, fake_push, "timer_end")


def test_no_device_writes_one_no_device_row(fake_push, caplog):
    caplog.set_level(logging.INFO)
    n = make_notification("timer_end")
    dispatch_module.dispatch(n, now=NOW)
    caplog.clear()
    dispatch_module.dispatch(n, now=NOW + timedelta(seconds=5))  # a replay updates the row, it does not add one
    assert_suppressed(n, "no_device", caplog, fake_push, "timer_end")
    assert rows(n)[0].attempted_at == NOW + timedelta(seconds=5)


def test_a_removed_device_is_not_sent_to(fake_push, device):
    device_service.remove_device(USER, device.id)
    result = dispatch_module.dispatch(make_notification("timer_end"), now=NOW)
    assert result.reason.value == "no_device" and fake_push.sent == []


def test_sending_switch_off_suppresses_with_flag_off(fake_push, device, caplog, monkeypatch):
    monkeypatch.setattr("modules.notifications.flags.sending_enabled", lambda user_id: False)
    caplog.set_level(logging.INFO)
    n = make_notification("timer_end")
    dispatch_module.dispatch(n, now=NOW)
    assert_suppressed(n, "flag_off", caplog, fake_push, "timer_end")


def test_event_kill_switch_suppresses_only_that_event(fake_push, device, settings):
    settings.NOTIFICATIONS_DISABLED_EVENTS = frozenset({"daily_nudge"})
    off = dispatch_module.dispatch(make_notification("daily_nudge"), now=NOW)
    on = dispatch_module.dispatch(make_notification("timer_end"), now=NOW)
    assert off.reason.value == "flag_off" and on.outcome == "sent" and len(fake_push.sent) == 1


def test_exempt_push_older_than_five_minutes_is_stale(fake_push, device, caplog):
    caplog.set_level(logging.INFO)
    n = make_notification("timer_end")
    dispatch_module.dispatch(n, now=NOW, intended_at=NOW - timedelta(minutes=6))
    assert_suppressed(n, "stale", caplog, fake_push, "timer_end")


def test_exempt_push_just_inside_five_minutes_is_sent_and_measures_lateness(fake_push, device):
    n = make_notification("timer_end")
    dispatch_module.dispatch(n, now=NOW, intended_at=NOW - timedelta(minutes=4, seconds=59))
    assert Delivery.objects.get().lateness_ms == 299_000 and len(fake_push.sent) == 1


def test_expired_non_exempt_notification_is_stale(fake_push, device):
    n = make_notification("daily_nudge", expires_at=NOW - timedelta(minutes=1))
    assert dispatch_module.dispatch(n, now=NOW).reason.value == "stale"


def test_quiet_hours_defer_non_exempt_without_sending(fake_push, device):
    n = make_notification("daily_nudge", expires_at=NIGHT + timedelta(hours=12))
    result = dispatch_module.dispatch(n, now=NIGHT)
    assert (result.action, result.outcome) == (Action.DEFER, "deferred")
    assert result.deliver_at == datetime(2026, 10, 6, 1, 30, tzinfo=UTC)  # 07:00 in India
    (row,) = rows(n)
    assert row.status == "queued" and row.device_id is None and row.suppress_reason is None
    assert fake_push.sent == []


def test_quiet_hours_that_outlast_the_expiry_suppress(fake_push, device, caplog):
    caplog.set_level(logging.INFO)
    n = make_notification("daily_nudge", expires_at=NIGHT + timedelta(hours=1))
    dispatch_module.dispatch(n, now=NIGHT)
    assert_suppressed(n, "quiet_hours", caplog, fake_push, "daily_nudge")


def test_exempt_events_ignore_quiet_hours(fake_push, device):
    assert dispatch_module.dispatch(make_notification("timer_end"), now=NIGHT).outcome == "sent"


def test_daily_cap_suppresses_the_fourth_and_priority_one_gets_one_extra(fake_push, device):
    for _ in range(3):
        sent_row(USER)
    assert dispatch_module.dispatch(make_notification("revision_due"), now=NOW).reason.value == "cap"
    assert dispatch_module.dispatch(make_notification("goal_reached"), now=NOW).outcome == "sent"
    assert dispatch_module.dispatch(make_notification("goal_reached"), now=NOW).reason.value == "cap"


def test_timer_alerts_do_not_use_the_cap_and_ignore_it(fake_push, device):
    for _ in range(5):
        sent_row(USER)
    assert dispatch_module.dispatch(make_notification("timer_end"), now=NOW).outcome == "sent"


def test_cap_counts_notifications_not_devices_and_only_the_local_day(fake_push):
    register(USER, now=NOW)
    register(USER, now=NOW)
    first = make_notification("daily_nudge")
    dispatch_module.dispatch(first, now=NOW)  # one notification, two devices
    assert Delivery.objects.filter(status="sent", counts_toward_cap=True).count() == 2
    sent_row(USER, at=NOW - timedelta(hours=5))  # 05:00 in India: still today
    yesterday_local = datetime(2026, 10, 4, 18, 0, tzinfo=UTC)  # 23:30 on 4 Oct in India
    for _ in range(5):
        sent_row(USER, at=yesterday_local)
    assert dispatch_module.dispatch(make_notification("daily_nudge"), now=NOW).outcome == "sent"  # 2 used before it
    assert dispatch_module.dispatch(make_notification("daily_nudge"), now=NOW).reason.value == "cap"  # 3 used


def test_cap_ignores_other_students_and_failed_rows(fake_push, device):
    for _ in range(4):
        sent_row(OTHER)
    n = make_notification("daily_nudge")
    Delivery.objects.create(
        notification=n,
        user_id=USER,
        device=device,
        channel="push",
        status="failed",
        counts_toward_cap=False,
        attempted_at=NOW,
    )
    assert dispatch_module.dispatch(make_notification("daily_nudge"), now=NOW).outcome == "sent"


# --- failures and device health ----------------------------------------------------------------------------------


def test_gone_marks_the_row_failed_revokes_the_device_and_logs_both(fake_push, device, caplog):
    healthy = register(USER, now=NOW).device
    fake_push.result_for = lambda s: SendResult.gone(410) if s.endpoint == device.endpoint_enc else None
    caplog.set_level(logging.INFO)
    n = make_notification("timer_end")
    result = dispatch_module.dispatch(n, now=NOW)
    assert (result.sent, result.failed, result.revoked, result.outcome) == (1, 1, 1, "sent")
    bad = Delivery.objects.get(notification=n, device=device)
    assert (bad.status, bad.http_status, bad.error_code, bad.counts_toward_cap) == ("failed", 410, "gone", False)
    d = Device.objects.get(id=device.id)
    assert d.revoked_at == NOW and d.revoked_reason == "gone"
    assert Device.objects.get(id=healthy.id).revoked_at is None
    assert Delivery.objects.get(notification=n, device=healthy).status == "sent"
    (failed,) = log_lines(caplog, "push_failed")
    (revoked,) = log_lines(caplog, "push_device_revoked")
    assert failed.push == {"event": "timer_end", "http_status": 410, "reason": "gone"}
    assert revoked.push == {"event": "timer_end", "http_status": 410, "reason": "gone"}


def test_a_gone_result_without_a_status_still_revokes(fake_push, device):
    from modules.notifications.channels import SendStatus

    fake_push.script(SendResult(SendStatus.GONE, None, "gone"))
    dispatch_module.dispatch(make_notification("timer_end"), now=NOW)
    assert Device.objects.get(id=device.id).revoked_reason == "gone" and Delivery.objects.get().http_status == 410


def test_transient_failure_counts_but_does_not_revoke(fake_push, device, caplog):
    fake_push.script(SendResult.failed("server_error", 503, attempts=3))
    caplog.set_level(logging.INFO)
    n = make_notification("daily_nudge")
    result = dispatch_module.dispatch(n, now=NOW)
    assert (result.sent, result.failed, result.revoked, result.outcome) == (0, 1, 0, "failed")
    row = Delivery.objects.get()
    assert (row.status, row.http_status, row.error_code, row.attempt, row.counts_toward_cap) == (
        "failed",
        503,
        "server_error",
        3,
        False,
    )
    d = Device.objects.get(id=device.id)
    assert (d.consecutive_failures, d.first_failure_at, d.last_failure_at, d.revoked_at) == (1, NOW, NOW, None)
    assert log_lines(caplog, "push_device_revoked") == []
    (failed,) = log_lines(caplog, "push_failed")
    assert failed.push == {"event": "daily_nudge", "http_status": 503, "reason": "server_error"}


def test_five_failures_over_a_week_revoke_the_device(fake_push, device, caplog):
    fake_push.default = SendResult.failed("server_error", 503)
    caplog.set_level(logging.INFO)
    for day in (0, 2, 4, 6):
        dispatch_module.dispatch(make_notification("timer_end"), now=NOW + timedelta(days=day))
    assert Device.objects.get(id=device.id).revoked_at is None
    dispatch_module.dispatch(make_notification("timer_end"), now=NOW + timedelta(days=8))
    d = Device.objects.get(id=device.id)
    assert d.revoked_reason == "failures" and d.consecutive_failures == 5
    (revoked,) = log_lines(caplog, "push_device_revoked")
    assert revoked.push["reason"] == "failures"
    fake_push.sent.clear()
    assert (
        dispatch_module.dispatch(make_notification("timer_end"), now=NOW + timedelta(days=9)).reason.value
        == "no_device"
    )
    assert fake_push.sent == []


def test_a_success_in_between_resets_the_failure_run(fake_push, device):
    fake_push.script(SendResult.failed("server_error", 503), SendResult.sent())
    dispatch_module.dispatch(make_notification("timer_end"), now=NOW)
    dispatch_module.dispatch(make_notification("timer_end"), now=NOW + timedelta(minutes=1))
    assert Device.objects.get(id=device.id).consecutive_failures == 0


def test_an_adapter_crash_fails_that_device_only_and_logs_the_class_not_the_message(fake_push, device, caplog):
    other = register(USER, now=NOW).device
    fake_push.script(RuntimeError(f"boom {device.endpoint_enc}"))
    caplog.set_level(logging.INFO)
    n = make_notification("timer_end")
    result = dispatch_module.dispatch(n, now=NOW)
    assert (result.sent, result.failed) == (1, 1)
    assert Delivery.objects.get(notification=n, device=device).error_code == "unexpected"
    assert Delivery.objects.get(notification=n, device=other).status == "sent"
    assert "RuntimeError" in caplog.text and device.endpoint_enc not in caplog.text


def test_missing_vapid_configuration_propagates_and_does_not_penalise_the_device(fake_push, device):
    fake_push.script(ChannelNotConfigured("no key"))
    n = make_notification("timer_end")
    with pytest.raises(ChannelNotConfigured):
        dispatch_module.dispatch(n, now=NOW)
    d = Device.objects.get(id=device.id)
    assert d.consecutive_failures == 0 and d.revoked_at is None
    assert Delivery.objects.get().status == "queued"
    # once configuration is fixed, the retry completes the same row
    dispatch_module.dispatch(n, now=NOW + timedelta(seconds=30))
    assert Delivery.objects.count() == 1 and Delivery.objects.get().status == "sent"


# --- retries and idempotency -------------------------------------------------------------------------------------


def test_a_retry_updates_the_same_row_and_does_not_resend_what_was_delivered(fake_push, device):
    second = register(USER, now=NOW).device
    fake_push.result_for = lambda s: (
        SendResult.failed("server_error", 503, attempts=3) if s.endpoint == device.endpoint_enc else None
    )
    n = make_notification("timer_end")
    dispatch_module.dispatch(n, now=NOW)
    first_ids = {r.device_id: r.id for r in rows(n)}
    assert {r.status for r in rows(n)} == {"sent", "failed"}
    fake_push.result_for = None
    fake_push.sent.clear()
    result = dispatch_module.dispatch(n, now=NOW + timedelta(seconds=30))
    assert (result.sent, result.already_sent, result.outcome) == (1, 1, "sent")
    assert len(fake_push.sent) == 1 and fake_push.sent[0][0].endpoint == device.endpoint_enc
    assert {r.device_id: r.id for r in rows(n)} == first_ids  # same rows, no new ones
    healed = Delivery.objects.get(notification=n, device=device)
    assert healed.status == "sent" and healed.error_code is None and healed.sent_at == NOW + timedelta(seconds=30)
    assert Delivery.objects.get(notification=n, device=second).sent_at == NOW


def test_replaying_a_fully_delivered_notification_sends_nothing_and_writes_nothing(fake_push, device):
    n = make_notification("daily_nudge")
    dispatch_module.dispatch(n, now=NOW)
    for _ in range(3):
        sent_row(USER)  # the cap is now reached by others, so a naive re-decision would suppress the replay
    before = [(r.id, r.status) for r in rows()]
    fake_push.sent.clear()
    result = dispatch_module.dispatch(n, now=NOW + timedelta(minutes=1))
    assert result.outcome == "already_sent" and fake_push.sent == []
    assert [(r.id, r.status) for r in rows()] == before


def test_a_retry_is_not_blocked_by_its_own_cap_slot(fake_push):
    register(USER, now=NOW)
    b = register(USER, now=NOW).device
    for _ in range(2):
        sent_row(USER)
    fake_push.result_for = lambda s: SendResult.failed("timeout") if s.endpoint == b.endpoint_enc else None
    n = make_notification("daily_nudge")
    dispatch_module.dispatch(n, now=NOW)  # 3rd slot used by `a`
    fake_push.result_for = None
    assert dispatch_module.dispatch(n, now=NOW + timedelta(minutes=1)).outcome == "sent"
    assert Delivery.objects.get(notification=n, device=b).status == "sent"


def test_a_later_send_replaces_the_earlier_suppressed_or_queued_placeholder(fake_push):
    n = make_notification("timer_end")
    dispatch_module.dispatch(n, now=NOW)  # no device yet
    assert Delivery.objects.get().suppress_reason == "no_device"
    register(USER, now=NOW)
    dispatch_module.dispatch(n, now=NOW + timedelta(seconds=10))
    (row,) = rows(n)
    assert row.status == "sent" and row.device_id is not None


def test_only_device_id_limits_the_send(fake_push, device):
    other = register(USER, now=NOW).device
    result = dispatch_module.dispatch(make_notification("test_push"), now=NOW, only_device_id=other.id)
    assert result.sent == 1 and fake_push.endpoints == [other.endpoint_enc]


# --- nothing secret in the logs ------------------------------------------------------------------------------------


def test_no_log_line_carries_an_endpoint_key_or_body(fake_push, device, caplog):
    other = register(USER, now=NOW).device
    fake_push.script(SendResult.gone(), SendResult.sent())
    caplog.set_level(logging.DEBUG)
    dispatch_module.dispatch(make_notification("timer_end"), now=NOW)
    dispatch_module.dispatch(make_notification("daily_nudge"), now=NIGHT)
    for secret in (
        device.endpoint_enc,
        device.p256dh_enc,
        device.auth_enc,
        other.endpoint_enc,
        "25 minutes on GST",
        "Round 2 done",
    ):
        assert secret not in caplog.text
    assert {r.getMessage().split(" ")[0] for r in caplog.records if r.name == dispatch_module.logger.name} >= {
        "push_failed",
        "push_device_revoked",
        "push_sent",
    }


# --- declarative push (FR-N35) -----------------------------------------------------------------------------------


def test_declarative_fields_are_off_by_default(fake_push, device):
    dispatch_module.dispatch(make_notification("timer_end", created_at=NOW), now=NOW)
    payload = json.loads(fake_push.sent[0][1].body)
    assert "web_push" not in payload and "notification" not in payload


def test_declarative_fields_are_added_when_switched_on(fake_push, device, settings):
    settings.NOTIFICATIONS_DECLARATIVE_PUSH = True
    settings.NOTIFICATIONS_WEB_BASE_URL = "https://app.example.com"
    n = make_notification("timer_end", created_at=NOW)
    dispatch_module.dispatch(n, now=NOW)
    payload = json.loads(fake_push.sent[0][1].body)
    assert payload["web_push"] == 8030
    assert payload["notification"]["navigate"] == f"https://app.example.com/app/focus?n={n.id}"
    assert payload["url"] == f"/app/focus?n={n.id}" and payload["tag"] == "timer:abc"  # the worker path is unchanged


def test_switching_it_on_without_a_web_origin_changes_nothing(fake_push, device, settings):
    settings.NOTIFICATIONS_DECLARATIVE_PUSH = True
    settings.NOTIFICATIONS_WEB_BASE_URL = ""
    dispatch_module.dispatch(make_notification("timer_end", created_at=NOW), now=NOW)
    assert "web_push" not in json.loads(fake_push.sent[0][1].body)
