"""
Channel registry. `apps.py` registers a factory per channel name; `get_channel` builds each adapter once, on first use,
so importing Django does not import `pywebpush`. Tests install a `FakeChannel` with `use_channel` and never reach the network.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from .base import (
    Channel,
    ChannelNotConfigured,
    DeviceSecrets,
    FakeChannel,
    PushMessage,
    SendResult,
    SendStatus,
    Urgency,
)
from .email import EMAIL, DjangoEmailChannel, EmailChannel, EmailMessage, FakeEmailChannel

PUSH = "push"

_factories: dict[str, Callable[[], Any]] = {}
_instances: dict[str, Any] = {}


class UnknownChannel(KeyError):
    pass


def register_channel(name: str, factory: Callable[[], Any]) -> None:
    _factories[name] = factory
    _instances.pop(name, None)


def use_channel(name: str, channel: Any) -> None:
    """Install a ready-made instance (tests, or a one-off script). Wins over the factory until `reset_channels`."""
    _instances[name] = channel


def get_channel(name: str = PUSH) -> Any:
    if name not in _instances:
        try:
            _instances[name] = _factories[name]()
        except KeyError:
            raise UnknownChannel(name) from None
    return _instances[name]


def reset_channels() -> None:
    """Forget built instances; factories stay registered."""
    _instances.clear()


__all__ = [
    "EMAIL",
    "PUSH",
    "Channel",
    "ChannelNotConfigured",
    "DeviceSecrets",
    "DjangoEmailChannel",
    "EmailChannel",
    "EmailMessage",
    "FakeChannel",
    "FakeEmailChannel",
    "PushMessage",
    "SendResult",
    "SendStatus",
    "UnknownChannel",
    "Urgency",
    "get_channel",
    "register_channel",
    "reset_channels",
    "use_channel",
]
