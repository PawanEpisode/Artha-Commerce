"""
The aggregated view (ERD 5 Q-2): "everything for Subject X", one keyset-paginated list over the item types a student has.
Each type is a *leg* with its own rank in the tie-break `(updated_at desc, rank, id)`. R1 has one leg, typed notes; R2 adds
highlights and documents by appending a leg to `LEGS`. Legs are fetched separately (each uses its own per-user index) and merged
here, which is the same result as a SQL `UNION ALL` without needing one query shape for different tables.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from ._common import (
    NoteCard,
    NoteFilter,
    Page,
    apply_filter,
    cards,
    clamp_limit,
    decode_cursor,
    encode_cursor,
    keyset_after,
    live_notes,
)
from .search import text_filter


@dataclass(frozen=True)
class AggregateItem:
    type: str  # "note" now; "highlight" and "document" in R2
    rank: int
    card: NoteCard


@dataclass(frozen=True)
class Leg:
    type: str
    rank: int
    tabs: frozenset[str]  # which `tab` values include this leg
    fetch: Callable[[object, NoteFilter, list | None, int], list[AggregateItem]]


def _notes_leg(user_id, flt: NoteFilter, cursor: list | None, limit: int) -> list[AggregateItem]:
    qs = text_filter(apply_filter(live_notes(user_id), flt), flt.q)
    qs = keyset_after(qs, ts_field="updated_at", rank=0, cursor=cursor).order_by("-updated_at", "id")
    return [AggregateItem("note", 0, card) for card in cards(list(qs[:limit]))]


LEGS: list[Leg] = [Leg("note", 0, frozenset({"all", "notes"}), _notes_leg)]


def aggregate(
    user_id, flt: NoteFilter, *, tab: str = "all", cursor: str | None = None, limit: int | None = None
) -> Page[AggregateItem]:
    limit = clamp_limit(limit)
    parts = decode_cursor(cursor)
    merged: list[AggregateItem] = []
    for leg in LEGS:
        if tab in leg.tabs:
            merged += leg.fetch(user_id, flt, parts, limit + 1)
    merged.sort(key=lambda i: (i.rank, str(i.card.note.id)))  # stable passes: tie-breaks first,
    merged.sort(key=lambda i: i.card.note.updated_at, reverse=True)  # then the timestamp, newest first
    page = merged[:limit]
    last = page[-1] if page else None
    more = len(merged) > limit and last is not None
    token = encode_cursor([last.card.note.updated_at, last.rank, last.card.note.id]) if more else None
    return Page(page, token)
