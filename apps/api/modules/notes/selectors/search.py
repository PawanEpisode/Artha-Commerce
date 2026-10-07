"""
Search over typed notes (ERD 5 Q-5, 6.3): per-student slice scan with the stored vector, no global index. A query matches in
either text configuration (English stems, or the simple one used for Hindi and mixed notes) and is ranked by cover density.
Highlights and PDF text are R2. On SQLite (tests) the vector is absent and a substring match stands in.
"""

from __future__ import annotations

from dataclasses import dataclass

from django.contrib.postgres.search import SearchQuery, SearchRank
from django.db import connection
from django.db.models import F, Q, QuerySet

from ..domain.search_query import clean_query, make_snippet, prepare_query, terms
from ..models import Note
from ._common import (
    NoteCard,
    NoteFilter,
    Page,
    apply_filter,
    cards,
    clamp_limit,
    decode_cursor,
    encode_cursor,
    live_notes,
)


@dataclass(frozen=True)
class SearchHit:
    card: NoteCard
    snippet: str
    rank: float


def _query(q: str):
    prepared = prepare_query(q)
    return SearchQuery(prepared, config="english", search_type="websearch") | SearchQuery(
        prepared, config="simple", search_type="websearch"
    )


def text_filter(qs: QuerySet[Note], q: str) -> QuerySet[Note]:
    """Notes whose title or text match `q` (PostgreSQL full text, or every term as a substring elsewhere)."""
    if not clean_query(q):
        return qs
    if connection.vendor == "postgresql":
        return qs.filter(search_tsv=_query(q))
    for term in terms(q):
        qs = qs.filter(Q(title__icontains=term) | Q(body_text__icontains=term))
    return qs


def search(
    user_id, q: str, *, scope: str = "all", flt: NoteFilter | None = None, limit: int = 20, cursor: str | None = None
) -> Page[SearchHit]:
    """Ranked hits (best first). The cursor is an offset: a rank order has no stable keyset. Scopes other than notes are empty in R1."""
    limit = clamp_limit(limit, 20)
    if scope not in ("all", "notes") or not clean_query(q):
        return Page([])
    offset = (decode_cursor(cursor) or [0])[0]
    qs = text_filter(apply_filter(live_notes(user_id), flt or NoteFilter()), q)
    if connection.vendor == "postgresql":
        qs = qs.annotate(rank=SearchRank(F("search_tsv"), _query(q), cover_density=True)).order_by(
            "-rank", "-updated_at", "id"
        )
    else:
        qs = qs.order_by("-updated_at", "id")
    rows = list(qs[offset : offset + limit + 1])
    more = len(rows) > limit
    rows = rows[:limit]
    words = terms(q)
    hits = [
        SearchHit(
            card, make_snippet(card.note.body_text or card.note.title, words), float(getattr(card.note, "rank", 0.0))
        )
        for card in cards(rows)
    ]
    return Page(hits, encode_cursor([offset + limit]) if more else None)
