"""
Web Push adapter: the only file that imports `pywebpush`. Encrypts the payload, signs it with our VAPID key, posts it
to the student's push service and turns every outcome into a `SendResult`.

  2xx             -> sent
  404, 410        -> gone (the subscription is dead; the caller revokes the device)
  429, 5xx        -> retried up to 3 attempts in total, waiting `Retry-After` (capped) or a short backoff, then failed
  timeout, network -> failed, not retried here (a slow push service must not hold a request for 3 x 5 s)
  other 4xx       -> failed at once (the push service rejected the request; retrying cannot help)

Nothing here logs, and no error text is kept: exceptions from `requests` and `pywebpush` carry the endpoint URL or the
response body, so only a short code survives.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from functools import lru_cache

import requests
from django.conf import settings
from py_vapid import Vapid, VapidException
from pywebpush import WebPushException, webpush

from .base import ChannelNotConfigured, DeviceSecrets, PushMessage, SendResult

TIMEOUT_SECONDS = 5
MAX_ATTEMPTS = 3
MAX_WAIT_SECONDS = 2.0  # cap on any single wait, so a hostile Retry-After cannot stall a serverless function
BACKOFF_SECONDS = (0.25, 0.75)  # before attempt 2 and 3 when the service gave no Retry-After
GONE_STATUSES = frozenset({404, 410})


@lru_cache(maxsize=4)
def _vapid_key(private_key: str) -> Vapid:
    try:
        return Vapid.from_string(private_key)
    except Exception:  # noqa: BLE001 - py_vapid raises several types; never echo the key in the message
        raise ChannelNotConfigured("VAPID_PRIVATE_KEY is not a valid VAPID key.") from None


def _vapid_settings() -> tuple[Vapid, str]:
    private_key = getattr(settings, "VAPID_PRIVATE_KEY", "")
    subject = getattr(settings, "VAPID_SUBJECT", "")
    if not private_key or not subject:
        raise ChannelNotConfigured("VAPID_PRIVATE_KEY and VAPID_SUBJECT must be set to send push messages.")
    if not subject.startswith("mailto:"):
        raise ChannelNotConfigured("VAPID_SUBJECT must be a mailto: address.")
    return _vapid_key(private_key), subject


def _retry_after_seconds(response: requests.Response | None) -> float | None:
    raw = None if response is None else response.headers.get("Retry-After")
    try:
        return max(0.0, float(raw)) if raw is not None else None
    except ValueError:  # an HTTP date: not worth parsing, fall back to the backoff
        return None


class WebPushChannel:
    def __init__(
        self,
        *,
        session: requests.Session | None = None,
        sleep: Callable[[float], None] = time.sleep,
        send_fn: Callable[..., object] = webpush,
    ):
        self._session = session
        self._sleep = sleep
        self._send_fn = send_fn

    def send(self, device_secrets: DeviceSecrets, message: PushMessage) -> SendResult:
        vapid_key, subject = _vapid_settings()
        result = SendResult.failed("unknown")
        for attempt in range(1, MAX_ATTEMPTS + 1):
            result, wait = self._attempt(device_secrets, message, vapid_key, subject, attempt)
            if wait is None:  # final: sent, gone, or a failure that retrying cannot fix
                return result
            if attempt < MAX_ATTEMPTS:
                self._sleep(min(wait, MAX_WAIT_SECONDS))
        return result

    def _attempt(
        self, secrets: DeviceSecrets, message: PushMessage, vapid_key: Vapid, subject: str, attempt: int
    ) -> tuple[SendResult, float | None]:
        """One POST. The second value is how long to wait before retrying, or None when the outcome is final."""
        try:
            response = self._send_fn(
                subscription_info={
                    "endpoint": secrets.endpoint,
                    "keys": {"p256dh": secrets.p256dh, "auth": secrets.auth},
                },
                data=message.body,
                vapid_private_key=vapid_key,
                vapid_claims={"sub": subject},  # a fresh dict each time: pywebpush adds `aud` and `exp` to it
                ttl=message.ttl_seconds,
                timeout=TIMEOUT_SECONDS,
                headers={"Urgency": message.urgency.value},
                requests_session=self._session,
            )
        except WebPushException as exc:
            return self._from_status(getattr(exc.response, "status_code", None), exc.response, attempt)
        except VapidException:  # signing refused our claims: a configuration problem, not this device's
            raise ChannelNotConfigured("VAPID claims were rejected by the signer.") from None
        except requests.Timeout:
            return SendResult.failed("timeout", attempts=attempt), None
        except requests.RequestException:
            return SendResult.failed("network", attempts=attempt), None
        except (ValueError, TypeError):  # pywebpush could not encrypt: malformed keys or endpoint
            return SendResult.failed("bad_subscription", attempts=attempt), None
        status = getattr(response, "status_code", 201)
        return SendResult.sent(status, attempts=attempt), None

    @staticmethod
    def _from_status(status: int | None, response, attempt: int) -> tuple[SendResult, float | None]:
        if status in GONE_STATUSES:
            return SendResult.gone(status, attempts=attempt), None
        if status == 429 or (status is not None and status >= 500):
            code = "rate_limited" if status == 429 else "server_error"
            wait = _retry_after_seconds(response)
            if wait is None:
                wait = BACKOFF_SECONDS[min(attempt - 1, len(BACKOFF_SECONDS) - 1)]
            return SendResult.failed(code, status, attempts=attempt), wait
        if status in (401, 403):
            return SendResult.failed("unauthorized", status, attempts=attempt), None
        if status is None:
            return SendResult.failed("network", attempts=attempt), None
        return SendResult.failed("rejected", status, attempts=attempt), None
