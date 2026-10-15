"""
Practice picker and origin registries (F-06 ERD 3.3).
"""

from __future__ import annotations

import random
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any


@dataclass(frozen=True)
class PickedItem:
    question_id: uuid.UUID
    version_id: uuid.UUID | None = None
    marks: Decimal | None = None
    negative_marks: Decimal | None = None
    section_label: str | None = None


@dataclass
class PickContext:
    user_id: uuid.UUID
    spec: dict[str, Any]
    rng: random.Random
    limit: int = 20


PickerFn = Callable[[PickContext], list[PickedItem]]


@dataclass
class OriginSpec:
    allowed_modes: set[str] = field(
        default_factory=lambda: {"untimed", "timed", "chapter_quiz", "revision", "custom_test", "exam"}
    )
    default_feedback_policy: str | None = None
    unique_per_user: bool = False
    title_for: Callable[[dict[str, Any]], str] | None = None
    validate_spec: Callable[[dict[str, Any]], None] | None = None


_PICKERS: dict[str, tuple[PickerFn, str]] = {}
_ORIGINS: dict[str, OriginSpec] = {}


def register_picker(name: str, fn: PickerFn, *, description: str) -> None:
    _PICKERS[name] = (fn, description)


def get_picker(name: str) -> PickerFn | None:
    entry = _PICKERS.get(name)
    return entry[0] if entry else None


def list_pickers() -> dict[str, str]:
    return {name: desc for name, (_, desc) in _PICKERS.items()}


def register_origin(name: str, spec: OriginSpec) -> None:
    _ORIGINS[name] = spec


def get_origin(name: str) -> OriginSpec | None:
    return _ORIGINS.get(name)
