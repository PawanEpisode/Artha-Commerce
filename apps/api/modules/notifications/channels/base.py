"""
The port every delivery channel implements, plus the fake used by tests. Dispatch depends on this file only, so a
provider change (or an email channel later) touches one adapter and nothing else.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Protocol, runtime_checkable


class ChannelNotConfigured(RuntimeError):
    """A channel's settings are missing or malformed. A deployment mistake, not a device problem: nobody is marked failed."""


class SendStatus(StrEnum):
    SENT = "sent"  # the push service accepted the message
    GONE = "gone"  # the subscription no longer exists (404 or 410): revoke the device
    FAILED = "failed"  # anything else, after the adapter's own retries


class Urgency(StrEnum):
    VERY_LOW = "very-low"
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"


@dataclass(frozen=True)
class DeviceSecrets:
    """Decrypted push credentials. Kept out of `repr` so a stray log line or traceback cannot leak them."""

    endpoint: str = field(repr=False)
    p256dh: str = field(repr=False)
    auth: str = field(repr=False)


@dataclass(frozen=True)
class PushMessage:
    body: str = field(repr=False)  # the encoded payload (JSON text)
    ttl_seconds: int = 3600  # how long the push service may hold it for an offline device
    urgency: Urgency = Urgency.NORMAL


@dataclass(frozen=True)
class SendResult:
    status: SendStatus
    http_status: int | None = None
    error_code: str | None = None  # short code only (`timeout`, `gone`, `rate_limited`), never a response body
    attempts: int = 1  # sends made inside the adapter, 1 to 3

    @classmethod
    def sent(cls, http_status: int = 201, attempts: int = 1) -> SendResult:
        return cls(SendStatus.SENT, http_status, None, attempts)

    @classmethod
    def gone(cls, http_status: int = 410, attempts: int = 1) -> SendResult:
        return cls(SendStatus.GONE, http_status, "gone", attempts)

    @classmethod
    def failed(cls, error_code: str, http_status: int | None = None, attempts: int = 1) -> SendResult:
        return cls(SendStatus.FAILED, http_status, error_code, attempts)


@runtime_checkable
class Channel(Protocol):
    def send(self, device_secrets: DeviceSecrets, message: PushMessage) -> SendResult: ...


class FakeChannel:
    """
    Records every send and answers from a script (FR-N31). With no script it accepts everything. `script` queues
    results (or exceptions to raise) consumed one per send; `result_for` decides per device when more control is needed.
    """

    def __init__(self, default: SendResult | None = None):
        self.default = default or SendResult.sent()
        self.sent: list[tuple[DeviceSecrets, PushMessage]] = []
        self._script: deque[SendResult | Exception] = deque()
        self.result_for: Callable[[DeviceSecrets], SendResult | None] | None = None

    def script(self, *results: SendResult | Exception) -> FakeChannel:
        self._script.extend(results)
        return self

    def send(self, device_secrets: DeviceSecrets, message: PushMessage) -> SendResult:
        self.sent.append((device_secrets, message))
        outcome = self._script.popleft() if self._script else None
        if outcome is None and self.result_for is not None:
            outcome = self.result_for(device_secrets)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome or self.default

    @property
    def endpoints(self) -> list[str]:
        return [secrets.endpoint for secrets, _ in self.sent]
