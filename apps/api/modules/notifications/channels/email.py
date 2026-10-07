"""
The email adapter (X-01.1 W3.5). Django's mail backend does the sending, so SMTP, a console backend for development and
the in-memory backend of the tests all work without a second code path. Nothing about the recipient is logged here.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from django.conf import settings
from django.core.mail import EmailMultiAlternatives

from .base import ChannelNotConfigured, SendResult

EMAIL = "email"


@dataclass(frozen=True)
class EmailMessage:
    to: str = field(repr=False)
    subject: str
    text: str = field(repr=False)
    html: str = field(repr=False)
    headers: dict[str, str] = field(default_factory=dict, repr=False)


@runtime_checkable
class EmailChannel(Protocol):
    def send(self, message: EmailMessage) -> SendResult: ...


class DjangoEmailChannel:
    def send(self, message: EmailMessage) -> SendResult:
        sender = getattr(settings, "NOTIFICATIONS_EMAIL_FROM", "")
        if not sender:
            raise ChannelNotConfigured("NOTIFICATIONS_EMAIL_FROM is not set")
        mail = EmailMultiAlternatives(
            subject=message.subject, body=message.text, from_email=sender, to=[message.to], headers=message.headers
        )
        mail.attach_alternative(message.html, "text/html")
        try:
            mail.send(fail_silently=False)
        except Exception as exc:  # noqa: BLE001 - any transport error is a failed attempt; keep only the class name
            return SendResult.failed(type(exc).__name__[:40].lower())
        return SendResult.sent(http_status=250)


class FakeEmailChannel:
    """Records every message and answers from a queue of results (tests; nothing here reaches a mail server)."""

    def __init__(self, default: SendResult | None = None):
        self.default = default or SendResult.sent(http_status=250)
        self.sent: list[EmailMessage] = []
        self.script: deque[SendResult | Exception] = deque()

    def send(self, message: EmailMessage) -> SendResult:
        self.sent.append(message)
        if self.script:
            step = self.script.popleft()
            if isinstance(step, Exception):
                raise step
            return step
        return self.default
