"""Shared read helpers: result types, opaque keyset cursors, the live-notes queryset and link/tag resolution for a page of notes."""

from __future__ import annotations

import base64
import json
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from typing import Any, Generic, TypeVar

from django.db.models import Exists, OuterRef, Q, QuerySet

from modules.syllabus import selectors as syllabus

from ..domain.quota import IST
from ..errors import BadCursor
from ..models import Document, DocumentChapter, ItemTag, Note, NoteImage, Tag

MAX_LIMIT = 100
T = TypeVar("T")


@dataclass(frozen=True)
class Page(Generic[T]):  # noqa: UP046 — `class Page[T]` is Python 3.12 syntax; 3.11 cannot import it
    items: list[T]
    next_cursor: str | None = None


@dataclass(frozen=True)
class LinkView:
    """Where a note sits in the syllabus, resolved by stable keys against the level's current scheme (see `cards`)."""

    level_id: Any = None
    subject_id: Any = None
    subject_key: str | None = None
    subject_name: str | None = None
    chapter_id: Any = None
    chapter_key: str | None = None
    chapter_name: str | None = None
    topic_id: Any = None
    topic_key: str | None = None
    topic_name: str | None = None
    moved_or_removed: bool = False


@dataclass(frozen=True)
class NoteCard:
    note: Note
    link: LinkView
    tags: tuple[Tag, ...] = ()
    image_ids: tuple[Any, ...] = ()


@dataclass(frozen=True)
class NoteFilter:
    """Filters shared by the notes list, the aggregated view and search. Keys need `level_id` (keys are per level)."""

    level_id: Any = None
    subject_key: str | None = None
    chapter_key: str | None = None
    topic_key: str | None = None
    tag_id: Any = None
    unfiled: bool = False
    kind: str | None = None
    pinned: bool | None = None
    q: str = ""
    date_from: date | None = None
    date_to: date | None = None
    extra: dict = field(default_factory=dict)


def clamp_limit(limit: int | None, default: int = 30) -> int:
    return max(1, min(limit or default, MAX_LIMIT))


# --- Cursors ----------------------------------------------------------------------------------------------------------
def encode_cursor(parts: Sequence[Any]) -> str:
    raw = json.dumps(
        [p.isoformat() if isinstance(p, datetime) else str(p) if not isinstance(p, int) else p for p in parts]
    )
    return base64.urlsafe_b64encode(raw.encode()).decode().rstrip("=")


def decode_cursor(cursor: str | None) -> list[Any] | None:
    if not cursor:
        return None
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        parts = json.loads(base64.urlsafe_b64decode(padded.encode()))
        if not isinstance(parts, list):
            raise ValueError
        return parts
    except (ValueError, UnicodeDecodeError) as exc:
        raise BadCursor from exc


def parse_ts(value: Any) -> datetime:
    try:
        return datetime.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise BadCursor from exc


# --- Querysets --------------------------------------------------------------------------------------------------------
def live_notes(user_id) -> QuerySet[Note]:
    return Note.objects.filter(user_id=user_id, deleted_at__isnull=True)


UNLISTED_DOCUMENT_STATUSES = (
    "reserved",
    "expired",
    "rejected",
)  # no file in the library: an upload that never finished


def live_documents(user_id) -> QuerySet[Document]:
    """Documents that count in a chapter or the aggregated view: not in the trash, and a real library entry."""
    return Document.objects.filter(user_id=user_id, deleted_at__isnull=True).exclude(
        status__in=UNLISTED_DOCUMENT_STATUSES
    )


def document_scope(qs: QuerySet[Document], f: NoteFilter) -> QuerySet[Document]:
    """
    Documents "in" a subject or chapter: by their own (default) link OR by a page range that maps pages to it. Documents and
    their ranges carry the same link columns, so one condition serves both. `unfiled` means no default and no range at all.
    """
    where = Q()
    if f.level_id:
        where &= Q(level_id=f.level_id)
    if f.subject_key:
        where &= Q(subject_key=f.subject_key)
    if f.chapter_key:
        where &= Q(chapter_key=f.chapter_key)
    if f.topic_key:
        where &= Q(topic_key=f.topic_key)
    ranged = DocumentChapter.objects.filter(document_id=OuterRef("pk"))
    if where:
        qs = qs.filter(where | Exists(ranged.filter(where)))
    if f.unfiled:
        qs = qs.filter(chapter__isnull=True).exclude(Exists(ranged))
    return qs


def day_start(day: date) -> datetime:
    return datetime.combine(day, time.min, tzinfo=IST)


def apply_filter(qs: QuerySet[Note], f: NoteFilter) -> QuerySet[Note]:
    """Every filter except text (`search.text_filter`), so list, aggregate and counts agree on what a filter means."""
    if f.level_id:
        qs = qs.filter(level_id=f.level_id)
    if f.subject_key:
        qs = qs.filter(subject_key=f.subject_key)
    if f.chapter_key:
        qs = qs.filter(chapter_key=f.chapter_key)
    if f.topic_key:
        qs = qs.filter(topic_key=f.topic_key)
    if f.tag_id:
        qs = qs.filter(item_tags__tag_id=f.tag_id)
    if f.unfiled:
        qs = qs.filter(chapter__isnull=True)
    if f.kind:
        qs = qs.filter(kind=f.kind)
    if f.pinned is not None:
        qs = qs.filter(pinned=f.pinned)
    if f.date_from:
        qs = qs.filter(updated_at__gte=day_start(f.date_from))
    if f.date_to:
        qs = qs.filter(updated_at__lt=day_start(f.date_to + timedelta(days=1)))
    return qs


def keyset_after(qs: QuerySet[Note], *, ts_field: str, rank: int, cursor: list[Any] | None) -> QuerySet[Note]:
    """
    Rows after `cursor` in the order (timestamp desc, leg rank asc, id asc). `cursor` is `[timestamp, leg_rank, id]`. A leg
    ranked after the cursor's leg also keeps rows with the same timestamp; a leg ranked before it does not.
    """
    if not cursor:
        return qs
    if len(cursor) != 3:
        raise BadCursor
    ts, cursor_rank, cursor_id = parse_ts(cursor[0]), cursor[1], str(cursor[2])
    if rank > cursor_rank:
        return qs.filter(**{f"{ts_field}__lte": ts})
    if rank < cursor_rank:
        return qs.filter(**{f"{ts_field}__lt": ts})
    return qs.filter(Q(**{f"{ts_field}__lt": ts}) | Q(**{ts_field: ts}, id__gt=cursor_id))


# --- Cards ------------------------------------------------------------------------------------------------------------
def cards(notes: Sequence[Note]) -> list[NoteCard]:
    """
    Notes with their tags and syllabus link, in a fixed number of queries. The link is resolved by stable keys against the
    level's CURRENT scheme, so a note filed under an old scheme shows under the equivalent chapter; when the key no longer
    exists the stored chapter names are used and `moved_or_removed` is true.
    """
    if not notes:
        return []
    tag_map: dict[Any, list[Tag]] = {}
    for item in ItemTag.objects.filter(note_id__in=[n.id for n in notes]).select_related("tag").order_by("tag__name"):
        tag_map.setdefault(item.note_id, []).append(item.tag)
    image_map: dict[Any, list[Any]] = {}
    for note_id, attachment_id in (
        NoteImage.objects.filter(note_id__in=[n.id for n in notes])
        .order_by("attachment_id")
        .values_list("note_id", "attachment_id")
    ):
        image_map.setdefault(note_id, []).append(attachment_id)
    links = link_views(notes)
    return [
        NoteCard(n, link, tuple(tag_map.get(n.id, ())), tuple(image_map.get(n.id, ())))
        for n, link in zip(notes, links, strict=True)
    ]


def link_views(rows: Sequence[Any]) -> list[LinkView]:
    """
    The syllabus link of any rows that carry link columns (notes, documents, marks, page ranges), one `LinkView` per row, in a
    fixed number of queries. See `cards` for the resolution rule (stable keys against the level's current scheme).
    """
    linked = [n for n in rows if n.chapter_id]
    current: dict[tuple, Any] = {}
    for level_id in {n.level_id for n in linked}:
        pairs = {(n.subject_key, n.chapter_key) for n in linked if n.level_id == level_id}
        for pair, ref in syllabus.resolve_key_pairs(level_id, pairs).items():
            current[(level_id, *pair)] = ref
    stored = syllabus.chapter_refs([n.chapter_id for n in linked])
    topics = syllabus.topic_refs([n.topic_id for n in linked if n.topic_id])
    return [_link(n, current, stored, topics) for n in rows]


def _link(note: Any, current: dict, stored: dict, topics: dict) -> LinkView:
    if not note.chapter_id:
        return LinkView()
    ref = current.get((note.level_id, note.subject_key, note.chapter_key))
    moved = ref is None
    ref = ref or stored.get(note.chapter_id)
    topic = topics.get(note.topic_id) if note.topic_id else None
    return LinkView(
        level_id=note.level_id,
        subject_id=ref.subject_id if ref else note.subject_id,
        subject_key=note.subject_key,
        subject_name=ref.subject_name if ref else None,
        chapter_id=ref.id if ref else note.chapter_id,
        chapter_key=note.chapter_key,
        chapter_name=ref.name if ref else None,
        topic_id=note.topic_id,
        topic_key=note.topic_key,
        topic_name=topic.name if topic else None,
        moved_or_removed=moved,
    )
