"""
Page ranges of a document and the marks that inherit from them (ERD 2.7, FR-F03-30).

`set_page_ranges` replaces the whole set under the document's row lock (so two devices cannot interleave a delete and an
insert), refuses overlaps (the pure check first, the database exclusion constraint as the last word) and then re-links the
marks. A mark's chapter is, in order: the one the student chose for it (`explicit`, never touched here), the range its page
is in (`range`), the document's default (`document`), none. `relink_marks` applies exactly `domain.chapter_inheritance`,
the function the web uses to show the chip before the write is accepted.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from django.db import IntegrityError, transaction
from django.utils import timezone

from .. import events
from ..domain import chapter_inheritance as inheritance
from ..errors import InvalidRange, RangesOverlap
from ..models import Annotation, Document, DocumentChapter
from . import links

EXCLUSION_VIOLATION = "23P01"
MAX_RANGES = 500
RELINK_BATCH = 1000


@dataclass(frozen=True)
class RelinkResult:
    count: int = 0
    keys: list = field(
        default_factory=list
    )  # old and new `(level, subject_key, chapter_key, chapter_id)` of what moved


@dataclass(frozen=True)
class RangesResult:
    ranges: list[DocumentChapter]
    relinked: int


def _is_exclusion(exc: IntegrityError) -> bool:
    cause = exc.__cause__
    return getattr(cause, "sqlstate", None) == EXCLUSION_VIOLATION or "notes_documentchapter" in str(exc)


COLUMNS = ("level_id", "subject_id", "chapter_id", "topic_id", "subject_key", "chapter_key", "topic_key")


def _columns(row) -> dict[str, Any]:
    """The link columns a range or document already holds. Reused as they are, so a relink never re-resolves the syllabus."""
    return {name: getattr(row, name) for name in COLUMNS}


def relink_marks(document: Document) -> RelinkResult:
    """
    Recomputes the link of every mark of the document that did not get its chapter from the student (`chapter_source` is not
    `explicit`) from the current ranges and default. Only marks whose link changes are written. Returns how many and the chapter
    keys involved (old and new), so the caller can announce the counts once.
    """
    range_rows = list(DocumentChapter.objects.filter(document=document).order_by("page_from"))
    ranges = [{"page_from": r.page_from, "page_to": r.page_to, "chapter": r} for r in range_rows]
    default = document if document.chapter_id else None
    marks = Annotation.objects.filter(document=document).exclude(chapter_source=Annotation.ChapterSource.EXPLICIT)
    moves: dict[
        tuple, tuple[dict[str, Any], str, list]
    ] = {}  # (chapter id, topic id, source) -> (columns, source, ids)
    keys: list = []
    for mark in marks.only("id", "page", "level", "subject_key", "chapter", "chapter_key", "topic", "chapter_source"):
        source_row, source = inheritance.effective_link(mark.page, None, ranges, default)
        columns = _columns(source_row) if source_row is not None else dict(links.UNLINKED)
        if (mark.chapter_id, mark.topic_id, mark.chapter_source) == (
            columns["chapter_id"],
            columns["topic_id"],
            source,
        ):
            continue
        group = (columns["chapter_id"], columns["topic_id"], source)
        moves.setdefault(group, (columns, source, []))[2].append(mark.id)
        keys += [links.link_key(mark), links.columns_key(columns)]
    now, moved = timezone.now(), 0
    seq = None
    if (
        moves
    ):  # one new `seq` for the whole move (the document is locked), so other devices' delta feeds pick the marks up
        document.change_seq += 1
        seq = document.change_seq
        Document.objects.filter(pk=document.pk).update(change_seq=seq)
    for columns, source, mark_ids in moves.values():
        for start in range(0, len(mark_ids), RELINK_BATCH):
            moved += Annotation.objects.filter(pk__in=mark_ids[start : start + RELINK_BATCH]).update(
                **columns, chapter_source=source, updated_at=now, seq=seq
            )
    return RelinkResult(moved, [k for k in keys if k])


def _validated(ranges: Sequence[dict[str, Any]], page_count: int | None) -> None:
    if len(ranges) > MAX_RANGES:
        raise InvalidRange("Too many page ranges.", extra={"limit": MAX_RANGES})
    problem = inheritance.validate_ranges(ranges)
    if problem and problem["code"] == "invalid_range":
        raise InvalidRange(extra={"index": problem["a"]})
    if problem:
        raise RangesOverlap(extra={"a": problem["a"], "b": problem["b"]})
    if page_count:
        for index, r in enumerate(ranges):
            if r["page_to"] > page_count:
                raise InvalidRange(
                    "That range goes past the last page.", extra={"index": index, "page_count": page_count}
                )


@transaction.atomic
def set_page_ranges(user_id, document_id, ranges: Sequence[dict[str, Any]]) -> RangesResult:
    from .documents import get_locked  # local: documents imports this module for `relink_marks`

    document = get_locked(user_id, document_id)
    _validated(ranges, document.page_count)
    rows: list[DocumentChapter] = []
    cache: dict[tuple, dict[str, Any]] = {}
    for r in ranges:
        key = (r["chapter_id"], r.get("topic_id"))
        if key not in cache:
            cache[key] = links.link_columns(*key)
        rows.append(
            DocumentChapter(
                id=uuid.uuid4(),
                user_id=user_id,
                document=document,
                page_from=r["page_from"],
                page_to=r["page_to"],
                source=r.get("source") or DocumentChapter.Source.USER,
                **cache[key],
            )
        )
    before = list(DocumentChapter.objects.filter(document=document).values_list("page_from", "page_to", "chapter_id"))
    try:
        with transaction.atomic():
            DocumentChapter.objects.filter(document=document).delete()
            DocumentChapter.objects.bulk_create(rows)
    except IntegrityError as exc:
        if _is_exclusion(exc):
            raise RangesOverlap from exc
        raise
    result = relink_marks(document)
    document.save(update_fields=["updated_at"])
    if result.count or sorted(before) != sorted((r.page_from, r.page_to, r.chapter_id) for r in rows):
        events.announce_counts(user_id, result.keys, "relinked")
    stored = list(DocumentChapter.objects.filter(document=document).order_by("page_from"))
    return RangesResult(stored, result.count)
