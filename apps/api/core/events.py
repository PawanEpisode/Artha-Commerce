"""
Tiny synchronous domain-event bus.

A module that owns a fact publishes it with `emit(name, **payload)`; modules that care call `subscribe(name, fn)`
once at app start (`AppConfig.ready`). The publisher never imports its consumers, which keeps the dependency
direction clean (for example `coverage` announces `study_targets_changed` without knowing `profiles` exists).

A subscriber that raises never breaks the write that triggered it: the error is logged and the next subscriber runs.
This is the stand-in for the `core/events` outbox that F-06 will introduce; names and payloads stay the same then.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from collections.abc import Callable
from typing import Any

logger = logging.getLogger(__name__)

Subscriber = Callable[..., None]

_subscribers: dict[str, list[Subscriber]] = defaultdict(list)


def subscribe(name: str, fn: Subscriber) -> None:
    """Idempotent: registering the same function twice for one event has no effect (app `ready()` can run twice)."""
    if fn not in _subscribers[name]:
        _subscribers[name].append(fn)


def emit(name: str, **payload: Any) -> None:
    for fn in list(_subscribers.get(name, ())):
        try:
            fn(**payload)
        except Exception:  # noqa: BLE001 - a consumer must never roll back or fail the publisher's write
            logger.exception("Subscriber %s failed for event %s", getattr(fn, "__name__", fn), name)


def clear() -> None:
    """Test helper."""
    _subscribers.clear()
