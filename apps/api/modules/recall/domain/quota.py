"""Plan limits as plain data (PRD 8.3). The numbers live in `recall_quotaplan`; `FREE` is only the safe fallback."""

from __future__ import annotations

from dataclasses import dataclass, fields


@dataclass(frozen=True)
class Limits:
    max_cards: int
    max_cards_per_deck: int
    max_decks: int
    max_active_shares: int
    ai_suggestions_per_day: int
    ai_batches_per_day: int
    share_imports_per_day: int
    pack_size: int

    @classmethod
    def names(cls) -> tuple[str, ...]:
        return tuple(f.name for f in fields(cls))


# Used when the plan row is missing: a missing row must never mean "unlimited".
FREE = Limits(
    max_cards=1500,
    max_cards_per_deck=500,
    max_decks=100,
    max_active_shares=20,
    ai_suggestions_per_day=30,
    ai_batches_per_day=3,
    share_imports_per_day=30,
    pack_size=300,
)
