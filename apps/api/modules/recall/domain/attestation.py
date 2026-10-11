"""The "my own words" statement (FR-F15-21) as plain rules: which cards it applies to and what its state reads as."""

from __future__ import annotations

from datetime import datetime

#: Item origins that start private and may be attested. Manual cards are hers already; imports are never shareable (R2-W3).
ATTESTABLE_ORIGINS = ("selection", "solution", "mistake")


def required(ownership: str, origin: str) -> bool:
    """Whether the statement applies: her own item that was made from a selection, a solution or a mistake."""
    return ownership == "user" and origin in ATTESTABLE_ORIGINS


def state_of(ownership: str, origin: str, shareable: bool, attested_at: datetime | None) -> dict:
    need = required(ownership, origin)
    attested = need and shareable and attested_at is not None
    return {"required": need, "attested": attested, "attested_at": attested_at if attested else None}
