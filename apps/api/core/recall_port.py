"""
The recall port (F-03 ERD 3.2, slice 19): how Smart Notes asks the recall module (F-15) for a flashcard without importing it.

F-15 is not built yet. Until it registers a provider, `get_recall_provider()` answers None and notes shows its "Make a
card" action as unavailable (503 `recall_unavailable`, `capabilities.recall = false`). When F-15 lands it calls
`register_recall_provider(provider)` from its `AppConfig.ready`; nothing in notes changes. Same shape as `core.registry`:
the dependency points at `core`, never from one feature module to another.

A provider implements `RecallProvider`:

- `create_card_from_source` is idempotent on `(user_id, source.ref_id, kind)` and on `client_id`: a second call for the
  same mark and kind returns the first card with `existing=True`.
- `cards_for_source` maps source ids to the cards that already exist for them.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable
from uuid import UUID

CARD_KINDS = ("formula", "rule", "definition", "example", "doubt", "fact")


@dataclass(frozen=True)
class SourceRef:
    """What a card was made from. `ref_id` is the id of the mark or note; never any of its text."""

    module: str
    ref_type: str
    ref_id: UUID
    label: str = ""


@dataclass(frozen=True)
class CardRef:
    id: UUID
    existing: bool = False


class RecallUnavailable(Exception):
    """Raised by a provider (or `NullRecallProvider`) that cannot make cards right now."""


@runtime_checkable
class RecallProvider(Protocol):
    def create_card_from_source(
        self,
        user_id: Any,
        *,
        kind: str,
        front_md: str,
        back_md: str,
        chapter_id: UUID | None = None,
        topic_id: UUID | None = None,
        source: SourceRef,
        client_id: UUID,
    ) -> CardRef: ...

    def cards_for_source(self, user_id: Any, ref_ids: Sequence[UUID]) -> Mapping[UUID, CardRef]: ...


class NullRecallProvider:
    """The explicit "no recall module" state: it cannot make cards and knows none. Treated like an absent provider."""

    def create_card_from_source(self, user_id: Any, **kwargs: Any) -> CardRef:
        raise RecallUnavailable

    def cards_for_source(self, user_id: Any, ref_ids: Sequence[UUID]) -> Mapping[UUID, CardRef]:
        return {}


_provider: RecallProvider | None = None


def register_recall_provider(provider: RecallProvider | None) -> None:
    """Install the provider (None removes it; tests use that to reset). The last registration wins."""
    global _provider
    _provider = provider


def get_recall_provider() -> RecallProvider | None:
    """The registered provider, or None when recall is absent (nothing registered, or the Null provider)."""
    return None if isinstance(_provider, NullRecallProvider) else _provider
