"""
Account-data registry (PRD F-16 FR-F16-39, closes audit finding AUD-004).

Every module that stores student data registers ONE eraser and ONE exporter when its app starts (`AppConfig.ready`).
Account export and deletion call every registered function, so a new module can never be forgotten and the account
service never imports the modules it erases. Lives in `core` so modules register without importing `profiles`.

- eraser:   `fn(user_id) -> dict` removes everything the module holds for the student and reports counts. Idempotent.
- exporter: `fn(user_id) -> dict` returns everything the module holds for the student (JSON-serialisable).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

UserFn = Callable[[Any], dict]

_erasers: dict[str, UserFn] = {}
_exporters: dict[str, UserFn] = {}


def register_eraser(name: str, fn: UserFn) -> None:
    _erasers[name] = fn


def register_exporter(name: str, fn: UserFn) -> None:
    _exporters[name] = fn


def erasers() -> list[tuple[str, UserFn]]:
    """Reverse registration order: apps start in dependency order, so dependents are erased before what they use."""
    return list(reversed(_erasers.items()))


def exporters() -> list[tuple[str, UserFn]]:
    return list(_exporters.items())
