"""The Web Push adapter against a fake HTTP session. pywebpush really encrypts and signs; only the network is faked."""

import base64
import logging

import pytest
import requests
from cryptography.hazmat.primitives.asymmetric import ec

from modules.notifications.channels import ChannelNotConfigured, DeviceSecrets, PushMessage, SendStatus, Urgency
from modules.notifications.channels.base import Channel, FakeChannel
from modules.notifications.channels.webpush import MAX_WAIT_SECONDS, TIMEOUT_SECONDS, WebPushChannel, _vapid_key
from modules.notifications.tests.helpers import make_endpoint, make_keys


def _vapid_private_key() -> str:
    key = ec.generate_private_key(ec.SECP256R1())
    raw = key.private_numbers().private_value.to_bytes(32, "big")
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


@pytest.fixture(autouse=True)
def _vapid(settings):
    _vapid_key.cache_clear()
    settings.VAPID_PRIVATE_KEY = _vapid_private_key()
    settings.VAPID_SUBJECT = "mailto:alerts@example.com"


class FakeSession:
    """Answers each POST from a script of (status, headers) or an exception to raise."""

    def __init__(self, *script):
        self.script = list(script) or [(201, {})]
        self.calls = []

    def post(self, url, **kwargs):
        self.calls.append({"url": url, **kwargs})
        step = self.script.pop(0) if len(self.script) > 1 else self.script[0]
        if isinstance(step, Exception):
            raise step
        status, headers = step
        response = requests.Response()
        response.status_code = status
        response.headers.update(headers)
        response._content = b"SECRET-BODY-FROM-PUSH-SERVICE"
        return response


def make(*script):
    session, sleeps = FakeSession(*script), []
    return WebPushChannel(session=session, sleep=sleeps.append), session, sleeps


def secrets(endpoint=None):
    keys = make_keys()
    return DeviceSecrets(endpoint or make_endpoint(), keys["p256dh"], keys["auth"])


def message(**kw):
    return PushMessage(body='{"v":1,"title":"hello"}', **kw)


def test_success_sends_an_encrypted_signed_request_with_ttl_urgency_and_timeout():
    channel, session, sleeps = make((201, {}))
    target = secrets()
    result = channel.send(target, message(ttl_seconds=300, urgency=Urgency.HIGH))
    assert (result.status, result.http_status, result.error_code, result.attempts) == (SendStatus.SENT, 201, None, 1)
    (call,) = session.calls
    assert call["url"] == target.endpoint and call["timeout"] == TIMEOUT_SECONDS == 5
    headers = {k.lower(): v for k, v in call["headers"].items()}
    assert headers["ttl"] == "300" and headers["urgency"] == "high"
    assert headers["authorization"].startswith("vapid t=") and "k=" in headers["authorization"]
    assert headers["content-encoding"] == "aes128gcm"
    assert b"hello" not in call["data"]  # the body is encrypted, never sent in the clear
    assert sleeps == []


@pytest.mark.parametrize("status", [404, 410])
def test_404_and_410_mean_gone_and_are_not_retried(status):
    channel, session, sleeps = make((status, {}))
    result = channel.send(secrets(), message())
    assert (result.status, result.http_status, result.error_code) == (SendStatus.GONE, status, "gone")
    assert len(session.calls) == 1 and sleeps == []


def test_429_waits_for_retry_after_then_succeeds():
    channel, session, sleeps = make((429, {"Retry-After": "1"}), (201, {}))
    result = channel.send(secrets(), message())
    assert result.status is SendStatus.SENT and result.attempts == 2 and result.http_status == 201
    assert len(session.calls) == 2 and sleeps == [1.0]


def test_retry_after_is_capped():
    channel, _, sleeps = make((429, {"Retry-After": "86400"}), (201, {}))
    channel.send(secrets(), message())
    assert sleeps == [MAX_WAIT_SECONDS]


@pytest.mark.parametrize("header", [{}, {"Retry-After": "Wed, 21 Oct 2026 07:28:00 GMT"}, {"Retry-After": "-5"}])
def test_missing_dated_or_negative_retry_after_uses_short_backoff(header):
    channel, _, sleeps = make((503, header), (201, {}))
    assert channel.send(secrets(), message()).status is SendStatus.SENT
    assert len(sleeps) == 1 and 0 <= sleeps[0] <= MAX_WAIT_SECONDS


def test_5xx_is_retried_three_times_then_fails_with_the_last_status():
    channel, session, sleeps = make((503, {}), (502, {}), (500, {}))
    result = channel.send(secrets(), message())
    assert (result.status, result.http_status, result.error_code, result.attempts) == (
        SendStatus.FAILED,
        500,
        "server_error",
        3,
    )
    assert len(session.calls) == 3 and len(sleeps) == 2  # no wait after the final attempt


def test_429_exhausted_reports_rate_limited():
    channel, session, _ = make((429, {}))
    result = channel.send(secrets(), message())
    assert (result.error_code, result.http_status, result.attempts) == ("rate_limited", 429, 3)
    assert len(session.calls) == 3


def test_gone_after_a_retry_still_counts_as_gone():
    channel, _, _ = make((503, {}), (410, {}))
    result = channel.send(secrets(), message())
    assert result.status is SendStatus.GONE and result.attempts == 2


@pytest.mark.parametrize(
    "status, code", [(400, "rejected"), (413, "rejected"), (401, "unauthorized"), (403, "unauthorized")]
)
def test_other_client_errors_fail_at_once(status, code):
    channel, session, sleeps = make((status, {}))
    result = channel.send(secrets(), message())
    assert (result.status, result.http_status, result.error_code, result.attempts) == (
        SendStatus.FAILED,
        status,
        code,
        1,
    )
    assert len(session.calls) == 1 and sleeps == []


def test_timeout_fails_with_a_code_and_is_not_retried():
    channel, session, _ = make(requests.ConnectTimeout("https://fcm.googleapis.com/secret-endpoint timed out"))
    result = channel.send(secrets(), message())
    assert (result.status, result.error_code, result.http_status) == (SendStatus.FAILED, "timeout", None)
    assert len(session.calls) == 1


def test_connection_error_fails_as_network():
    channel, _, _ = make(requests.ConnectionError("dns failure for https://fcm.googleapis.com/secret"))
    assert channel.send(secrets(), message()).error_code == "network"


def test_malformed_keys_fail_as_bad_subscription_without_a_request():
    channel, session, _ = make((201, {}))
    bad = DeviceSecrets(make_endpoint(), "not-a-key", "also-not")
    result = channel.send(bad, message())
    assert result.status is SendStatus.FAILED and result.error_code == "bad_subscription"
    assert session.calls == []


def test_nothing_secret_survives_in_the_result_or_the_logs(caplog):
    caplog.set_level(logging.DEBUG)
    target = secrets()
    for script in ([(410, {})], [(500, {})], [requests.Timeout(target.endpoint)], [(201, {})]):
        channel, _, _ = make(*script)
        result = channel.send(target, message())
        text = repr(result) + repr(target) + repr(message())
        assert target.endpoint not in text and target.auth not in text and "hello" not in text
        assert "SECRET-BODY" not in text
    assert target.endpoint not in caplog.text and target.auth not in caplog.text and "SECRET-BODY" not in caplog.text


@pytest.mark.parametrize(
    "private_key, subject",
    [("", "mailto:a@example.com"), ("x", ""), ("garbage", "mailto:a@example.com"), (None, None)],
)
def test_missing_or_malformed_vapid_settings_raise_not_configured(settings, private_key, subject):
    settings.VAPID_PRIVATE_KEY, settings.VAPID_SUBJECT = private_key, subject
    _vapid_key.cache_clear()
    channel, session, _ = make((201, {}))
    with pytest.raises(ChannelNotConfigured) as caught:
        channel.send(secrets(), message())
    assert str(private_key or "-") not in str(caught.value) or private_key == ""
    assert session.calls == []


@pytest.mark.parametrize("subject", ["alerts@example.com", "https://example.com/contact"])
def test_vapid_subject_must_be_a_mailto_address(settings, subject):
    settings.VAPID_SUBJECT = subject
    with pytest.raises(ChannelNotConfigured):
        make((201, {}))[0].send(secrets(), message())


def test_injected_send_function_receives_a_fresh_claims_dict_each_attempt():
    seen = []

    def fake_send(**kwargs):
        seen.append(kwargs["vapid_claims"])
        kwargs["vapid_claims"]["aud"] = "mutated"  # pywebpush does this to the dict it is given
        response = requests.Response()
        response.status_code = 201
        return response

    result = WebPushChannel(send_fn=fake_send).send(secrets(), message())
    assert result.status is SendStatus.SENT and seen == [{"sub": "mailto:alerts@example.com", "aud": "mutated"}]
    WebPushChannel(send_fn=fake_send).send(secrets(), message())
    assert seen[1] is not seen[0]


# --- the port and its fake -----------------------------------------------------------------------------------------


def test_adapter_and_fake_satisfy_the_channel_protocol():
    assert isinstance(WebPushChannel(), Channel) and isinstance(FakeChannel(), Channel)


def test_fake_channel_records_scripts_and_raises():
    from modules.notifications.channels import SendResult

    fake = FakeChannel().script(SendResult.gone(), RuntimeError("boom"))
    target = secrets()
    assert fake.send(target, message()).status is SendStatus.GONE
    with pytest.raises(RuntimeError):
        fake.send(target, message())
    assert fake.send(target, message()).status is SendStatus.SENT  # script used up: the default answers
    assert fake.endpoints == [target.endpoint] * 3
