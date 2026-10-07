"""
The aggregated view (ERD 5 Q-2): "everything for Subject X", one keyset-paginated list over the item types a student has.
Each type is a *leg* with its own rank in the tie-break `(updated_at desc, rank, id)`: typed notes (0), marks that carry text or
meaning (1, `type: "highlight"`) and documents (2). Every leg is read separately with the cursor applied (each uses its own
per-student index) and the legs are merged here by that same key, which equals the SQL `UNION ALL ... ORDER BY updated_at DESC,
kind_rank, id` of the ERD without forcing one column shape on three tables. Each leg is asked for `limit + 1` rows, so the merge
of the legs' heads is the true head of the union and a page boundary can never skip or repeat a row, whichever filter is set.

`color` and `doc` only make sense for marks: with either set, the other legs are empty (the list then shows that colour or
that document's marks, not "notes in the same chapter").
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import datetime
from typing import Any

from django.db.models import Q

from ..domain.search_query import clean_query, terms
from ..models import Annotation
from ._common import (
    NoteFilter,
    Page,
    apply_filter,
    cards,
    clamp_limit,
    decode_cursor,
    document_scope,
    encode_cursor,
    keyset_after,
    live_documents,
    live_notes,
)
from .annotations import annotation_cards, live_marks
from .annotations import text_filter as mark_text_filter
from .documents import document_views
from .search import text_filter

NOTE_RANK, MARK_RANK, DOCUMENT_RANK = 0, 1, 2


@dataclass(frozen=True)
class AggregateItem:
    type: str  # "note" | "highlight" | "document"
    rank: int
    updated_at: datetime
    item_id: Any
    card: Any  # NoteCard | AnnotationCard | DocumentView


@dataclass(frozen=True)
class Leg:
    type: str
    rank: int
    tabs: frozenset[str]  # which `tab` values include this leg
    fetch: Callable[[object, NoteFilter, list | None, int], list[AggregateItem]]


def _marks_only(flt: NoteFilter) -> bool:
    return bool(flt.extra.get("color") or flt.extra.get("doc"))


def _notes_leg(user_id, flt: NoteFilter, cursor: list | None, limit: int) -> list[AggregateItem]:
    if _marks_only(flt):
        return []
    qs = text_filter(apply_filter(live_notes(user_id), flt), flt.q)
    qs = keyset_after(qs, ts_field="updated_at", rank=NOTE_RANK, cursor=cursor).order_by("-updated_at", "id")
    return [AggregateItem("note", NOTE_RANK, c.note.updated_at, c.note.id, c) for c in cards(list(qs[:limit]))]


def _marks_leg(user_id, flt: NoteFilter, cursor: list | None, limit: int) -> list[AggregateItem]:
    qs = live_marks(user_id).filter(kind__in=Annotation.LISTED_KINDS)
    qs = apply_filter(qs, replace(flt, kind=None, pinned=None))
    qs = mark_text_filter(qs, flt.q)
    if flt.extra.get("color"):
        qs = qs.filter(color=flt.extra["color"])
    if flt.extra.get("doc"):
        qs = qs.filter(document_id=flt.extra["doc"])
    qs = keyset_after(qs, ts_field="updated_at", rank=MARK_RANK, cursor=cursor).order_by("-updated_at", "id")
    return [
        AggregateItem("highlight", MARK_RANK, c.annotation.updated_at, c.annotation.id, c)
        for c in annotation_cards(list(qs[:limit]))
    ]


def _documents_leg(user_id, flt: NoteFilter, cursor: list | None, limit: int) -> list[AggregateItem]:
    if _marks_only(flt) or flt.kind or flt.pinned is not None:  # a note-only filter excludes documents too
        return []
    # tag and date filters are the common ones; the chapter keys are matched by default link or page range below
    qs = apply_filter(
        live_documents(user_id),
        replace(flt, level_id=None, subject_key=None, chapter_key=None, topic_key=None, unfiled=False),
    )
    qs = document_scope(qs, flt)
    if clean_query(flt.q):
        for term in terms(flt.q):
            qs = qs.filter(Q(title__icontains=term) | Q(original_filename__icontains=term))
    qs = keyset_after(qs, ts_field="updated_at", rank=DOCUMENT_RANK, cursor=cursor).order_by("-updated_at", "id")
    return [
        AggregateItem("document", DOCUMENT_RANK, v.document.updated_at, v.document.id, v)
        for v in document_views(user_id, list(qs[:limit]))
    ]


LEGS: list[Leg] = [
    Leg("note", NOTE_RANK, frozenset({"all", "notes"}), _notes_leg),
    Leg("highlight", MARK_RANK, frozenset({"all", "highlights"}), _marks_leg),
    Leg("document", DOCUMENT_RANK, frozenset({"all", "documents"}), _documents_leg),
]


def aggregate(
    user_id, flt: NoteFilter, *, tab: str = "all", cursor: str | None = None, limit: int | None = None
) -> Page[AggregateItem]:
    limit = clamp_limit(limit)
    parts = decode_cursor(cursor)
    merged: list[AggregateItem] = []
    for leg in LEGS:
        if tab in leg.tabs:
            merged += leg.fetch(user_id, flt, parts, limit + 1)
    merged.sort(key=lambda i: (i.rank, str(i.item_id)))  # stable passes: tie-breaks first,
    merged.sort(key=lambda i: i.updated_at, reverse=True)  # then the timestamp, newest first
    page = merged[:limit]
    last = page[-1] if page else None
    more = len(merged) > limit and last is not None
    token = encode_cursor([last.updated_at, last.rank, last.item_id]) if more else None
    return Page(page, token)
