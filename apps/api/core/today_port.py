"""
The Today port (F-13 does not exist yet): how a module offers "what to do today" without importing the Today module.

A module that has study tasks registers ONE provider from its `AppConfig.ready`:

    register_task_provider("recall", provide_today)        # provide_today(user_id, *, now) -> ProviderResult | None

and Today (F-13), when it is built, calls `collect(user_id, now=now)` once per load. The shape is the same as `core.plans` and
`core.recall_port`: the dependency points at `core`, never from one feature module to another.

A provider answers an object with a `key` (str) and `tasks` (a sequence of tasks that carry at least `kind`, `title`, `count` and
`est_minutes`). The port does not look inside the tasks, so each module keeps its own dataclasses. Three rules keep Today safe:

- a provider that raises never breaks Today: the error is logged (no student data in it) and that provider is skipped,
- a provider that answers None, or nothing, simply has nothing to show (a module whose flag is off answers an empty result),
- `NullTaskProvider` is the explicit "nothing here" state, and `collect` with no provider registered answers an empty list.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Sequence
from datetime import datetime
from typing import Any, Protocol, runtime_checkable

logger = logging.getLogger(__name__)


@runtime_checkable
class TaskResult(Protocol):
    key: str
    tasks: Sequence[Any]


TaskProvider = Callable[..., "TaskResult | None"]


def NullTaskProvider(user_id: Any, *, now: datetime) -> None:  # noqa: N802 - named like the other ports' null adapters
    """The explicit "no tasks": what a module with nothing to offer registers (or what F-13 gets when nothing is registered)."""
    return None


_providers: dict[str, TaskProvider] = {}


def register_task_provider(key: str, fn: TaskProvider | None) -> None:
    """Install (or, with None, remove) the provider of `key`. Idempotent: the last registration of a key wins."""
    if fn is None:
        _providers.pop(key, None)
    else:
        _providers[key] = fn


def registered_keys() -> list[str]:
    return sorted(_providers)


def collect(user_id: Any, *, now: datetime) -> list[TaskResult]:
    """Every registered provider's result for this student, in key order. A failing or empty provider is left out."""
    out: list[TaskResult] = []
    for key in sorted(_providers):
        try:
            result = _providers[key](user_id, now=now)
        except Exception:  # noqa: BLE001 - one module's failure must never blank the whole Today screen
            logger.warning("Today provider %s failed", key, exc_info=True)
            continue
        if result is not None and len(result.tasks) > 0:
            out.append(result)
    return out


def clear() -> None:
    """Test helper."""
    _providers.clear()
