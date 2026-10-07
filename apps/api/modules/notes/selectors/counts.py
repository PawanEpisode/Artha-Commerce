"""
Counts per chapter and the chapter overview (ERD 5 Q-3, Q-4, Q-20). Always computed from the live rows of the student, grouped
by the stable `(level, subject_key, chapter_key)`: there is no derived table that could drift, and a scheme switch needs no
migration of counts. Highlights, marks and documents are 0 until R2 adds their tables.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from django.db.models import Count, Max, Q

from modules.syllabus import selectors as syllabus

from ..models import Note
from ._common import NoteCard, cards, live_notes


@dataclass(frozen=True)
class ChapterCounts:
    notes: int = 0
    highlights: int = 0
    marks: int = 0
    documents: int = 0
    has_summary: bool = False
    last_noted_at: datetime | None = None


@dataclass(frozen=True)
class ChapterCountRow:
    chapter_id: UUID
    chapter_key: str
    name: str
    counts: ChapterCounts


@dataclass(frozen=True)
class SubjectCounts:
    subject_key: str
    chapters: list[ChapterCountRow]
    unfiled: int
    moved_or_removed: list[ChapterCountRow] = field(default_factory=list)


@dataclass(frozen=True)
class ChapterOverview:
    chapter: syllabus.ChapterRef
    counts: ChapterCounts
    current_summary: NoteCard | None
    recent: list[NoteCard]


def _grouped(user_id, where: Q) -> dict[tuple, ChapterCounts]:
    rows = (
        live_notes(user_id)
        .filter(where, chapter__isnull=False)
        .order_by()
        .values("level_id", "subject_key", "chapter_key")
        .annotate(
            notes=Count("id", filter=Q(kind="note")),
            summaries=Count("id", filter=Q(kind="exam_summary", is_current_summary=True)),
            last=Max("updated_at", filter=Q(kind="note")),
        )
    )
    return {
        (r["level_id"], r["subject_key"], r["chapter_key"]): ChapterCounts(
            notes=r["notes"], has_summary=r["summaries"] > 0, last_noted_at=r["last"]
        )
        for r in rows
    }


def chapter_counts(user_id, level_id, subject_key: str, chapter_key: str) -> ChapterCounts:
    """Counts of one chapter by its stable keys (what the event subscriber and the chapter slot read)."""
    where = Q(level_id=level_id, subject_key=subject_key, chapter_key=chapter_key)
    return _grouped(user_id, where).get((level_id, subject_key, chapter_key), ChapterCounts())


def counts_for_chapters(user_id, chapter_ids: Sequence[UUID]) -> dict[UUID, ChapterCounts]:
    """For F-02's chapter page, Today and analytics: counts by chapter id, resolved through the chapter's stable keys."""
    refs = syllabus.chapter_refs(list(chapter_ids))
    if not refs:
        return {}
    where = Q()
    for ref in refs.values():
        where |= Q(level_id=ref.level_id, subject_key=ref.subject_key, chapter_key=ref.key)
    grouped = _grouped(user_id, where)
    return {cid: grouped.get((r.level_id, r.subject_key, r.key), ChapterCounts()) for cid, r in refs.items()}


def unfiled_count(user_id) -> int:
    return live_notes(user_id).filter(chapter__isnull=True).count()


def subject_counts(user_id, level_id, subject_key: str) -> SubjectCounts | None:
    """
    Counts for every chapter of a subject in the level's current scheme (zero rows included, syllabus order), the student's
    Unfiled count, and chapters the student has notes under that the current scheme no longer has (`moved_or_removed`).
    None when the subject is not in the level's current scheme and the student has no notes under it.
    """
    scheme_id = syllabus.current_scheme_id(level_id)
    current = syllabus.chapters_for_scheme(scheme_id, subject_key) if scheme_id else []
    grouped = _grouped(user_id, Q(level_id=level_id, subject_key=subject_key))
    rows = [
        ChapterCountRow(c.id, c.key, c.name, grouped.get((level_id, subject_key, c.key), ChapterCounts()))
        for c in current
    ]
    known = {c.key for c in current}
    missing = {key for (_, _, key) in grouped if key not in known}
    if not current and not missing:
        return None
    return SubjectCounts(
        subject_key, rows, unfiled_count(user_id), _removed_rows(user_id, level_id, subject_key, grouped, missing)
    )


def _removed_rows(user_id, level_id, subject_key, grouped, missing: set[str]) -> list[ChapterCountRow]:
    if not missing:
        return []
    pairs = (
        live_notes(user_id)
        .filter(level_id=level_id, subject_key=subject_key, chapter_key__in=missing)
        .order_by()
        .values_list("chapter_key", "chapter_id")
        .distinct()
    )
    stored = syllabus.chapter_refs([cid for _, cid in pairs])
    out: dict[str, ChapterCountRow] = {}
    for key, chapter_id in pairs:
        ref = stored.get(chapter_id)
        out.setdefault(
            key, ChapterCountRow(chapter_id, key, ref.name if ref else key, grouped[(level_id, subject_key, key)])
        )
    return sorted(out.values(), key=lambda r: r.name)


def chapter_overview(user_id, level_id, subject_key: str, chapter_key: str) -> ChapterOverview | None:
    """The chapter page slot: counts, the current exam summary and the latest notes. None when the key is not in the current scheme."""
    ref = syllabus.resolve_keys(level_id, subject_key, chapter_key)
    if ref is None:
        return None
    here = live_notes(user_id).filter(level_id=level_id, subject_key=subject_key, chapter_key=chapter_key)
    summary = here.filter(kind=Note.Kind.EXAM_SUMMARY, is_current_summary=True).first()
    recent = list(here.filter(kind=Note.Kind.NOTE).order_by("-updated_at", "id")[:5])
    carded = cards(([summary] if summary else []) + recent)
    return ChapterOverview(
        ref,
        chapter_counts(user_id, level_id, subject_key, chapter_key),
        carded[0] if summary else None,
        carded[1 if summary else 0 :],
    )
