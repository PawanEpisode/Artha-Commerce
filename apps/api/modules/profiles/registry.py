"""
Extension points of the profiles module (ERD section 3). Other modules call these at app start (`AppConfig.ready`):

- `register_onboarding_step(spec, handler)`: F-12 adds `coaching`, F-13 a planner step, X-01 a consent step.
  The `spec` (pure, `domain.onboarding.StepSpec`) says when the step is done; the `handler` saves it.
- Account export and erasure live in `core.registry` so modules register without importing this app.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from rest_framework.serializers import Serializer

from .domain.onboarding import BUILT_IN_STEPS, StepSpec


@dataclass(frozen=True)
class StepHandler:
    """Saves one step through the owning module's service. `apply(user, data)` returns nothing; errors are API errors."""

    serializer: type[Serializer]
    apply: Callable[[Any, dict], None]


_specs: dict[str, StepSpec] = {spec.key: spec for spec in BUILT_IN_STEPS}
_handlers: dict[str, StepHandler] = {}


def register_onboarding_step(spec: StepSpec, handler: StepHandler) -> None:
    _specs[spec.key] = spec
    _handlers[spec.key] = handler


def register_handler(key: str, handler: StepHandler) -> None:
    _handlers[key] = handler


def step_specs() -> list[StepSpec]:
    return list(_specs.values())


def get_spec(key: str) -> StepSpec | None:
    return _specs.get(key)


def get_handler(key: str) -> StepHandler | None:
    return _handlers.get(key)
