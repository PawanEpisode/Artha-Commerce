"""
The delayed queue and its signature check: the only file that imports `qstash` (PRD section 9.1, FR-N31).

`DelayedQueue` is the port: `publish(job_id, fire_at)` schedules one call to the job's fire URL and returns the queue's
message id; `cancel(external_id)` withdraws it (a courtesy: a job that was superseded is also skipped when it fires).
`NullQueue` records calls and is the default (local development, tests). `QStashQueue` is the production adapter.
Callers wrap every queue call so that a queue outage never fails a student's request; the per-minute sweep fires any
job whose message never arrived.

`SignatureVerifier` is the matching port for the inbound call. It verifies the `Upstash-Signature` JWT against the
current and next signing keys (rotation) and checks the body hash and the exact callback URL.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import datetime
from typing import Protocol
from uuid import UUID

import httpx
from django.conf import settings
from django.urls import reverse

from ..logs import log_event

logger = logging.getLogger(__name__)

FIRE_ROUTE = "notifications-internal-fire"
QSTASH_RETRIES = 3  # redeliveries after a 5xx; the handler is idempotent (atomic claim)
PUBLISH_TIMEOUT = httpx.Timeout(3.0, connect=2.0)  # this call runs inside a student's request: keep it short
DELIVERY_TIMEOUT_SECONDS = 15  # how long QStash waits for the fire endpoint


class QueueNotConfigured(RuntimeError):
    """`NOTIFICATIONS_QUEUE=qstash` without the token or the public base URL."""


class DelayedQueue(Protocol):
    def publish(self, job_id: UUID, fire_at: datetime) -> str: ...

    def cancel(self, external_id: str) -> None: ...


def fire_callback_url(job_id: UUID | str) -> str:
    """The absolute URL the queue calls (and the signature is bound to): public base URL plus the job's fire route."""
    base = getattr(settings, "NOTIFICATIONS_PUBLIC_BASE_URL", "")
    if not base:
        raise QueueNotConfigured("NOTIFICATIONS_PUBLIC_BASE_URL is not set")
    return base + reverse(FIRE_ROUTE, kwargs={"job_id": job_id})


class NullQueue:
    """Records calls and schedules nothing. `fail_with` makes every call raise, to rehearse a queue outage."""

    def __init__(self) -> None:
        self.published: list[tuple[UUID, datetime]] = []
        self.cancelled: list[str] = []
        self.fail_with: Exception | None = None

    def publish(self, job_id: UUID, fire_at: datetime) -> str:
        if self.fail_with:
            raise self.fail_with
        self.published.append((job_id, fire_at))
        return f"null-{job_id}"

    def cancel(self, external_id: str) -> None:
        if self.fail_with:
            raise self.fail_with
        self.cancelled.append(external_id)


class QStashQueue:
    """Upstash QStash. Message id is the external id; the job id is the deduplication id."""

    def __init__(self, token: str, *, base_url: str | None = None, client=None) -> None:
        if client is None:
            from qstash import QStash

            if not token:
                raise QueueNotConfigured("QSTASH_TOKEN is not set")
            client = QStash(token, retry=False, base_url=base_url or None)  # no SDK retries inside a request
            client.http._client.timeout = PUBLISH_TIMEOUT  # the SDK default is ten minutes
        self._client = client

    def publish(self, job_id: UUID, fire_at: datetime) -> str:
        response = self._client.message.publish_json(
            url=fire_callback_url(job_id),
            body={"job_id": str(job_id)},
            not_before=int(fire_at.timestamp()),
            retries=QSTASH_RETRIES,
            deduplication_id=str(job_id),
            timeout=DELIVERY_TIMEOUT_SECONDS,
        )
        return response.message_id

    def cancel(self, external_id: str) -> None:
        self._client.message.cancel(external_id)


# --- Factory -------------------------------------------------------------------------------------------------------
_instance: DelayedQueue | None = None


def _build() -> DelayedQueue:
    kind = getattr(settings, "NOTIFICATIONS_QUEUE", "null")
    if kind == "qstash":
        return QStashQueue(settings.QSTASH_TOKEN, base_url=settings.QSTASH_URL)
    if kind == "null":
        return NullQueue()
    raise QueueNotConfigured(f"Unknown NOTIFICATIONS_QUEUE value: {kind!r}")


def get_queue() -> DelayedQueue:
    global _instance
    if _instance is None:
        _instance = _build()
    return _instance


def use_queue(queue: DelayedQueue) -> None:
    """Install a ready-made queue (tests)."""
    global _instance
    _instance = queue


def reset_queue() -> None:
    global _instance
    _instance = None


# --- Inbound signature ---------------------------------------------------------------------------------------------
class SignatureVerifier(Protocol):
    def verify(self, *, signature: str, body: str, url: str) -> bool: ...


class QStashSignatureVerifier:
    """Receiver of the QStash SDK: JWT (HS256) with the current key, then the next key, body hash and URL checked."""

    def __init__(self, current_key: str, next_key: str, *, clock_tolerance: int = 5) -> None:
        from qstash import Receiver

        self._receiver = Receiver(current_key, next_key)
        self._tolerance = clock_tolerance

    def verify(self, *, signature: str, body: str, url: str) -> bool:
        from qstash.errors import SignatureError

        try:
            self._receiver.verify(signature=signature, body=body, url=url, clock_tolerance=self._tolerance)
        except SignatureError:
            return False
        except Exception:  # noqa: BLE001 - anything unexpected while checking a signature is a rejection
            log_event(logging.WARNING, "signature_check_error")
            return False
        return True


class _RejectAll:
    def verify(self, *, signature: str, body: str, url: str) -> bool:
        return False


VerifierFactory = Callable[[], SignatureVerifier]


def get_signature_verifier() -> SignatureVerifier:
    """Built from the signing keys in settings. Without both keys nothing can be verified, so everything is refused."""
    current = getattr(settings, "QSTASH_CURRENT_SIGNING_KEY", "")
    following = getattr(settings, "QSTASH_NEXT_SIGNING_KEY", "")
    if not (current and following):
        return _RejectAll()
    return QStashSignatureVerifier(current, following)
