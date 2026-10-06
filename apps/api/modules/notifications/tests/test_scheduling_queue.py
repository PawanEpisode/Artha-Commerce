"""The delayed-queue port: the recording fake, the QStash adapter (with a fake SDK client) and the factory."""

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

import httpx
import pytest

from modules.notifications.scheduling import queue

JOB = uuid.UUID("11111111-2222-3333-4444-555555555555")
FIRE_AT = datetime(2026, 10, 5, 4, 55, tzinfo=UTC)


def test_the_callback_url_is_the_public_origin_plus_the_fire_route():
    assert queue.fire_callback_url(JOB) == f"https://api.example.test/api/v1/notifications/internal/jobs/{JOB}/fire/"


def test_the_callback_url_needs_a_public_origin(settings):
    settings.NOTIFICATIONS_PUBLIC_BASE_URL = ""
    with pytest.raises(queue.QueueNotConfigured):
        queue.fire_callback_url(JOB)


def test_null_queue_records_publishes_and_cancels():
    q = queue.NullQueue()
    assert q.publish(JOB, FIRE_AT) == f"null-{JOB}"
    q.cancel("null-x")
    assert q.published == [(JOB, FIRE_AT)] and q.cancelled == ["null-x"]


def test_null_queue_can_rehearse_an_outage():
    q = queue.NullQueue()
    q.fail_with = RuntimeError("down")
    with pytest.raises(RuntimeError):
        q.publish(JOB, FIRE_AT)
    with pytest.raises(RuntimeError):
        q.cancel("x")
    assert q.published == [] and q.cancelled == []


class FakeMessages:
    def __init__(self):
        self.calls, self.cancelled = [], []

    def publish_json(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(message_id="msg_123", deduplicated=False)

    def cancel(self, message_id):
        self.cancelled.append(message_id)


def test_qstash_publish_sends_the_callback_not_before_time_retries_and_dedup_id():
    messages = FakeMessages()
    q = queue.QStashQueue("token", client=SimpleNamespace(message=messages))
    assert q.publish(JOB, FIRE_AT) == "msg_123"
    (call,) = messages.calls
    assert call["url"] == queue.fire_callback_url(JOB)
    assert call["not_before"] == int(FIRE_AT.timestamp())
    assert call["retries"] == queue.QSTASH_RETRIES == 3
    assert call["deduplication_id"] == str(JOB)  # one message per job, however often it is published
    assert call["body"] == {"job_id": str(JOB)}
    assert call["timeout"] == queue.DELIVERY_TIMEOUT_SECONDS


def test_qstash_cancel_deletes_the_message():
    messages = FakeMessages()
    queue.QStashQueue("token", client=SimpleNamespace(message=messages)).cancel("msg_123")
    assert messages.cancelled == ["msg_123"]


def test_the_real_sdk_client_is_built_with_a_short_timeout_and_no_hidden_retries():
    q = queue.QStashQueue("token", base_url="https://qstash.example.test")  # builds the SDK client, sends nothing
    http = q._client.http
    assert http._client.timeout == httpx.Timeout(3.0, connect=2.0)  # the SDK default is ten minutes
    assert http._retry["retries"] == 0
    assert http._base_url == "https://qstash.example.test"


def test_qstash_needs_a_token():
    with pytest.raises(queue.QueueNotConfigured):
        queue.QStashQueue("")


def test_the_factory_follows_the_setting(settings):
    queue.reset_queue()
    settings.NOTIFICATIONS_QUEUE = "null"
    assert isinstance(queue.get_queue(), queue.NullQueue)
    assert queue.get_queue() is queue.get_queue()  # built once
    queue.reset_queue()
    settings.NOTIFICATIONS_QUEUE = "qstash"
    settings.QSTASH_TOKEN, settings.QSTASH_URL = "token", ""
    assert isinstance(queue.get_queue(), queue.QStashQueue)
    queue.reset_queue()
    settings.NOTIFICATIONS_QUEUE = "carrier-pigeon"
    with pytest.raises(queue.QueueNotConfigured):
        queue.get_queue()


def test_no_other_module_imports_qstash():
    import pathlib

    root = pathlib.Path(__file__).resolve().parents[1]
    offenders = [
        str(path.relative_to(root))
        for path in root.rglob("*.py")
        if "tests" not in path.parts
        and path.name != "queue.py"
        and any(line.lstrip().startswith(("import qstash", "from qstash")) for line in path.read_text().splitlines())
    ]
    assert offenders == []
