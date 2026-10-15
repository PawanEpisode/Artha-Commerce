"""
Question bank extension registries (F-06 ERD 3.3).
Allows adding question kinds and file importers without modifying core code.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import dataclass
from typing import Any

from .domain.kinds import ALL_KINDS, KindSpec
from .domain.payload import QuestionPayload


@dataclass(frozen=True)
class ImporterSpec:
    fmt: str
    parse: Callable[[Any], Iterator[QuestionPayload | dict[str, Any]]]
    needs_ai: bool = False


_kinds: dict[str, KindSpec] = {}
_importers: dict[str, ImporterSpec] = {}


def register_kind(spec: KindSpec) -> None:
    """Registers a question kind specification."""
    _kinds[spec.name] = spec


def get_kind(name: str) -> KindSpec | None:
    """Returns the KindSpec for the given name or None if not registered."""
    return _kinds.get(name)


def registered_kinds() -> dict[str, KindSpec]:
    """Returns a copy of all registered kinds."""
    return dict(_kinds)


def register_importer(fmt: str, spec: ImporterSpec) -> None:
    """Registers a question file importer (csv, json, etc.)."""
    _importers[fmt] = spec


def get_importer(fmt: str) -> ImporterSpec | None:
    return _importers.get(fmt)


# Seed the 7 core kinds on import
for _spec in ALL_KINDS:
    register_kind(_spec)
