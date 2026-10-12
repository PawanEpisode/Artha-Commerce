"""
The suggestion source port (F-15 FR-F15-18): how recall asks other features for the student's OWN material of one chapter, so it
can draft cards from it, without importing them. Notes registers the `notes` source (her notes and highlights); the question bank
(F-06, not built yet) will register `wrong_answers`. A source that nobody registered answers None and the request is refused with
422 `source_unavailable`. Same shape as `core.question_port`: the dependency points at `core`, never between feature modules.

A provider answers `texts_for(user_id, chapter_id)` with the pieces of text it holds for that chapter and only that student. It
must enforce ownership itself and return plain text (no HTML). Recall never asks for more than `limit` pieces.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable
from uuid import UUID


@dataclass(frozen=True)
class SourcePiece:
    ref: str  # `note:<id>`, `mark:<id>`, `question:<id>`: an id and nothing else of hers
    label: str  # short and neutral, shown to the model and to her ("Note", "Highlight, page 12")
    text: str


@runtime_checkable
class SuggestionSourceProvider(Protocol):
    def texts_for(self, user_id: Any, chapter_id: UUID, *, limit: int) -> list[SourcePiece]: ...


_providers: dict[str, SuggestionSourceProvider] = {}


def register_suggestion_source(name: str, provider: SuggestionSourceProvider | None) -> None:
    """Install (or, with None, remove) the provider of one source name. The last registration wins."""
    if provider is None:
        _providers.pop(name, None)
    else:
        _providers[name] = provider


def get_suggestion_source(name: str) -> SuggestionSourceProvider | None:
    return _providers.get(name)


def available_sources() -> tuple[str, ...]:
    return tuple(sorted(_providers))
