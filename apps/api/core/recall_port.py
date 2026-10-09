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
- `available_for` (optional) says whether this student can use recall right now (a provider that is gated by a flag answers
  False for students outside it). `recall_available(user_id)` is what a caller asks; a provider without the method counts as on.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable
from uuid import UUID

from rest_framework import status

from core.errors import CodedError

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


class RecallUnavailable(CodedError):
    """
    Raised by a provider (or `NullRecallProvider`) that cannot make cards right now, for example because the student's recall
    flag is off. It is an API error in its own right (503 `recall_unavailable`, the same answer Notes gives when no provider is
    registered), so a caller that does not catch it still answers correctly instead of with a 500.
    """

    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_detail = "Flashcards are not available yet."
    default_code = "recall_unavailable"


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


def recall_available(user_id: Any) -> bool:
    """Whether recall works for this student: a provider is registered and (when it can tell) it is on for her. Never raises."""
    provider = get_recall_provider()
    if provider is None:
        return False
    check = getattr(provider, "available_for", None)
    if check is None:
        return True
    try:
        return bool(check(user_id))
    except Exception:  # noqa: BLE001 - a capability probe must never break a settings read
        return False
