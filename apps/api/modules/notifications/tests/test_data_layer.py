import uuid

import pytest
from django.db import IntegrityError, connection, transaction

from core import registry
from core.fields import hmac_hex
from modules.notifications.models import Delivery, Device, Notification, NotificationSettings, Preference, ScheduledJob
from modules.notifications.selectors.export import export_all
from modules.notifications.services.erasure import delete_all_for_user

pytestmark = pytest.mark.django_db
USER = uuid.uuid4()


@pytest.fixture(autouse=True)
def _crypto(settings):
    from cryptography.fernet import Fernet

    settings.FIELD_ENCRYPTION_KEYS = [Fernet.generate_key().decode()]
    settings.FIELD_HASH_PEPPER = "pepper-pepper-pepper"


def make_device(user=USER, endpoint="https://fcm.googleapis.com/x", **kw):
    return Device.objects.create(
        user_id=user,
        kind="web_push",
        endpoint_enc=endpoint,
        endpoint_hash=hmac_hex(endpoint),
        p256dh_enc="p",
        auth_enc="a",
        **kw,
    )


def make_notification(user=USER, key="k1"):
    return Notification.objects.create(
        user_id=user,
        category="timer",
        event="timer_end",
        dedupe_key=key,
        title="t",
        body="b",
        deep_link="/app/focus",
        priority=0,
    )


def fails(**kw):
    with pytest.raises(IntegrityError), transaction.atomic():
        kw.pop("make")()


def test_device_secrets_are_encrypted_at_rest():
    d = make_device()
    with connection.cursor() as c:
        c.execute(
            "select endpoint_enc, auth_enc from notifications_device where id = %s",
            [d.id.hex if connection.vendor == "sqlite" else d.id],
        )
        endpoint, auth = c.fetchone()
    assert "fcm.googleapis.com" not in endpoint and auth != "a"
    d.refresh_from_db()
    assert d.endpoint_enc == "https://fcm.googleapis.com/x" and d.auth_enc == "a"


def test_endpoint_hash_is_unique_and_web_push_needs_keys():
    make_device()
    fails(make=lambda: make_device(user=uuid.uuid4()))
    fails(make=lambda: Device.objects.create(user_id=USER, kind="web_push"))
    Device.objects.create(user_id=USER, kind="desktop_app")  # no keys needed


def test_notification_dedupe_priority_and_link_checks():
    make_notification()
    fails(make=lambda: make_notification())
    make_notification(user=uuid.uuid4())  # same key, other student: fine
    fails(
        make=lambda: Notification.objects.create(
            user_id=USER, category="timer", event="e", dedupe_key="p", title="t", body="b", deep_link="/app", priority=4
        )
    )
    fails(
        make=lambda: Notification.objects.create(
            user_id=USER,
            category="timer",
            event="e",
            dedupe_key="l",
            title="t",
            body="b",
            deep_link="//evil.com",
            priority=1,
        )
    )


def test_delivery_is_unique_even_without_a_device_and_suppressed_needs_a_reason():
    n = make_notification()
    Delivery.objects.create(
        notification=n, user_id=USER, channel="push", status="suppressed", suppress_reason="no_device"
    )
    if connection.vendor == "postgresql":  # `nulls_distinct=False` needs PostgreSQL 15+; SQLite ignores it
        fails(
            make=lambda: Delivery.objects.create(
                notification=n, user_id=USER, channel="push", status="suppressed", suppress_reason="no_device"
            )
        )
    fails(make=lambda: Delivery.objects.create(notification=n, user_id=USER, channel="email", status="suppressed"))


def test_settings_checks():
    fails(make=lambda: NotificationSettings.objects.create(user_id=USER, quiet_start="22:00", quiet_end="22:00"))
    fails(make=lambda: NotificationSettings.objects.create(user_id=uuid.uuid4(), permission_ask_count=4))
    fails(make=lambda: NotificationSettings.objects.create(user_id=uuid.uuid4(), permission_state="weird"))


def test_job_is_unique_per_timer_version():
    kw = dict(user_id=USER, kind="timer_end", subject_key="c1", expected_version=2, fire_at="2026-03-01T00:00:00Z")
    ScheduledJob.objects.create(**kw)
    fails(make=lambda: ScheduledJob.objects.create(**kw))
    ScheduledJob.objects.create(**{**kw, "expected_version": 3})


def test_eraser_and_exporter_are_registered_and_cover_everything():
    names = {name for name, _ in registry.erasers()}
    assert "notifications" in names and "notifications" in {n for n, _ in registry.exporters()}

    other = uuid.uuid4()
    n = make_notification()
    Delivery.objects.create(notification=n, user_id=USER, channel="push", status="queued")
    make_device()
    Preference.objects.create(user_id=USER, category="timer", channel="push", enabled=False)
    NotificationSettings.objects.create(user_id=USER)
    ScheduledJob.objects.create(user_id=USER, kind="timer_end", subject_key="c", fire_at="2026-03-01T00:00:00Z")
    make_notification(user=other, key="o")

    data = export_all(USER)
    assert len(data["notifications"]) == 1 and data["settings"] is not None
    assert "endpoint" not in str(data["devices"]) and "auth" not in str(data["devices"])

    counts = delete_all_for_user(USER)
    assert counts["devices"] == 1 and counts["settings"] == 1
    assert not Delivery.objects.exists() and Notification.objects.filter(user_id=other).count() == 1
    assert delete_all_for_user(USER)["notifications"] == 0  # idempotent
