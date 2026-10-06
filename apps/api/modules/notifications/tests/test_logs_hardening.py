"""W2.7 observability: no secret ever reaches a log line (PRD section 10) and every line carries Sentry tags (FR-N23)."""

import json
import logging
import uuid
from datetime import UTC, datetime, timedelta

import pytest
import sentry_sdk

from modules.notifications import dispatch as dispatch_module
from modules.notifications.channels import SendResult
from modules.notifications.domain.enums import JobKind
from modules.notifications.logs import log_event
from modules.notifications.models import Notification, ScheduledJob
from modules.notifications.scheduling import jobs, sweep
from modules.notifications.tests.helpers import make_endpoint, make_keys, register
from modules.notifications.tests.test_dispatch import USER, make_notification

pytestmark = pytest.mark.django_db
NOW = datetime(2026, 10, 5, 4, 30, tzinfo=UTC)
BODY = "Quadratic equations, 25 minutes with Rahul Sharma"


def pushed_text(caplog) -> str:
    """Every log line, message and structured fields together, as one string to search."""
    return "\n".join(f"{r.getMessage()} {json.dumps(getattr(r, 'push', {}), default=str)}" for r in caplog.records)


def test_no_log_line_holds_an_endpoint_a_key_or_the_notification_text(caplog, fake_push):
    endpoint, keys = make_endpoint(), make_keys()
    device = register(USER, endpoint=endpoint, keys=keys, now=NOW).device
    caplog.set_level(logging.DEBUG)

    # success, a failure that revokes the device, a suppression and a sweep, so every line type is exercised
    n = make_notification("timer_end", created_at=NOW)
    Notification.objects.filter(id=n.id).update(body=BODY)
    dispatch_module.dispatch(Notification.objects.get(id=n.id), now=NOW)
    fake_push.script(SendResult.gone())
    dispatch_module.dispatch(make_notification("timer_end", key="k2", created_at=NOW), now=NOW)
    ScheduledJob.objects.create(
        user_id=USER, kind=JobKind.TIMER_END, subject_key="s", fire_at=NOW - timedelta(minutes=1)
    )
    sweep.run_sweep(now=NOW)
    jobs.fire_job(uuid.uuid4(), now=NOW)

    text = pushed_text(caplog)
    assert "push_sent" in text and "push_device_revoked" in text and "sweep_run" in text
    for secret in (endpoint, keys["p256dh"], keys["auth"], BODY, "Rahul", str(device.endpoint_hash or "x" * 5)):
        assert secret not in text, f"log leaked {secret[:12]}"
    assert "fcm.googleapis.com" not in text


def test_log_fields_are_never_the_forbidden_names(caplog, fake_push):
    caplog.set_level(logging.DEBUG)
    register(USER, now=NOW)
    dispatch_module.dispatch(make_notification("timer_end", created_at=NOW), now=NOW)
    sweep.run_sweep(now=NOW)
    forbidden = {"endpoint", "p256dh", "auth", "token", "body", "title", "key", "keys", "secret", "subscription"}
    for record in caplog.records:
        assert forbidden.isdisjoint(getattr(record, "push", {})), record.getMessage()


@pytest.fixture
def sentry_events():
    events: list[dict] = []

    def keep(event, hint):
        events.append(event)
        return None  # dropped: nothing leaves the test

    sentry_sdk.init(dsn="http://public@localhost:9/1", before_send=keep, traces_sample_rate=0)
    yield events
    sentry_sdk.init(dsn=None)


def test_an_error_line_reaches_sentry_tagged_with_its_name_and_its_event(sentry_events):
    log_event(logging.ERROR, "push_failed", event="timer_end", http_status=500, reason="boom")
    (event,) = sentry_events
    assert event["tags"]["push_log"] == "push_failed" and event["tags"]["notification_event"] == "timer_end"


def test_a_line_without_an_event_is_tagged_by_name_only(sentry_events):
    log_event(logging.ERROR, "push_slo_breach", attempts=10)
    (event,) = sentry_events
    assert event["tags"]["push_log"] == "push_slo_breach" and "notification_event" not in event["tags"]


def test_tags_do_not_leak_into_the_next_event(sentry_events):
    log_event(logging.ERROR, "push_failed", event="timer_end")
    log_event(logging.ERROR, "push_slo_breach")
    assert "notification_event" not in sentry_events[1]["tags"]


def test_info_lines_do_not_create_sentry_events(sentry_events):
    log_event(logging.INFO, "push_sent", event="timer_end")
    assert sentry_events == []
