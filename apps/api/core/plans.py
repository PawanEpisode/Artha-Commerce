"""
The student's plan code, read through one function (F-15 decision D1). Until billing exists every student is on `free`.

Billing registers a provider from its `AppConfig.ready` (the same shape as `core.recall_port`); modules read the plan with
`plan_code_for(user_id)` and look their limits up by that code in their own plan table. Nothing here knows any module.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

DEFAULT_PLAN = "free"

_provider: Callable[[Any], str] | None = None


def register_plan_provider(provider: Callable[[Any], str] | None) -> None:
    """Install (or, with None, remove) the function that answers a student's plan code."""
    global _provider
    _provider = provider


def plan_code_for(user_id: Any) -> str:
    """The plan code of a student; `free` when no provider is registered or it answers nothing."""
    if _provider is None:
        return DEFAULT_PLAN
    return _provider(user_id) or DEFAULT_PLAN
