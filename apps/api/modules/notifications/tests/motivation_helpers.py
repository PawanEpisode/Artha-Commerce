"""Builders shared by the motivation tests (thought card, nudge, library)."""

import uuid
from datetime import UTC, datetime

from modules.notifications.domain.enums import MessageStatus
from modules.notifications.models import Message

USER = uuid.UUID("3f2b8c7e-6d2e-4f0e-9a45-0f9e5b3e1c11")
OTHER = uuid.UUID("7a1d2c3b-4e5f-4a6b-8c7d-9e0f1a2b3c4d")
THIRD = uuid.UUID("0b9f6a1e-2c3d-4e5f-8a7b-1c2d3e4f5a6b")
PUBLISHED_AT = datetime(2026, 9, 1, tzinfo=UTC)

_counter = iter(range(10_000))


def message(body=None, *, tone="calm", phase="any", status=MessageStatus.PUBLISHED, **kwargs) -> Message:
    """One library line; published by default (a draft or retired line is `status=`)."""
    n = next(_counter)
    return Message.objects.create(
        body=body or f"Line number {n}.",
        tone=tone,
        phase=phase,
        status=status,
        published_at=PUBLISHED_AT if status != MessageStatus.DRAFT else None,
        **kwargs,
    )


def library(count: int, **kwargs) -> list[Message]:
    return [message(f"General line {n:03d}.", **kwargs) for n in range(count)]
