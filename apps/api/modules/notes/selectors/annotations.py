"""
Reading marks (ERD Q-8, Q-10): the delta feed a reader syncs from, one mark by id, and the live-marks queryset the aggregated
view and the counts share. A mark counts as live when it is not a tombstone and its document is not in the trash.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from uuid import UUID

from django.db import connection
from django.db.models import Q, QuerySet

from ..domain.search_query import clean_query, prepare_query, terms
from ..models import Annotation, Document, ItemTag, Tag
from ._common import LinkView, link_views

MAX_DELTA = 500


@dataclass(frozen=True)
class AnnotationCard:
    annotation: Annotation
    link: LinkView
    tags: tuple[Tag, ...] = ()


@dataclass(frozen=True)
class AnnotationDelta:
    items: list[AnnotationCard]  # tombstones included, ordered by `seq`
    change_seq: int
    next_since_seq: int
    has_more: bool


def live_marks(user_id) -> QuerySet[Annotation]:
    return Annotation.objects.filter(user_id=user_id, deleted_at__isnull=True, document__deleted_at__isnull=True)


def annotation_cards(rows: Sequence[Annotation]) -> list[AnnotationCard]:
    """Marks with their tags and syllabus link in a fixed number of queries."""
    if not rows:
        return []
    tag_map: dict = {}
    for item in (
        ItemTag.objects.filter(annotation_id__in=[a.id for a in rows]).select_related("tag").order_by("tag__name")
    ):
        tag_map.setdefault(item.annotation_id, []).append(item.tag)
    return [
        AnnotationCard(a, link, tuple(tag_map.get(a.id, ()))) for a, link in zip(rows, link_views(rows), strict=True)
    ]


def get_annotation(user_id, annotation_id) -> AnnotationCard | None:
    row = Annotation.objects.filter(pk=annotation_id, user_id=user_id).first()
    return annotation_cards([row])[0] if row else None


def annotation_document_id(user_id, annotation_id) -> UUID | None:
    """The document a student's mark belongs to; None for a mark that is not theirs (or does not exist)."""
    return Annotation.objects.filter(pk=annotation_id, user_id=user_id).values_list("document_id", flat=True).first()


def delta_annotations(user_id, document_id, *, since_seq: int = 0, limit: int = MAX_DELTA) -> AnnotationDelta | None:
    """
    Marks of one document changed after `since_seq`, oldest change first, with tombstones. None when the document is not the
    student's. `change_seq` is read BEFORE the rows: a write that lands in between only makes the next call repeat a mark
    (harmless), never skip one. A page never ends inside a group of rows sharing one `seq` (a bulk re-link stamps them
    together), so `next_since_seq` is always safe to resume from.
    """
    change_seq = Document.objects.filter(pk=document_id, user_id=user_id).values_list("change_seq", flat=True).first()
    if change_seq is None:
        return None
    limit = max(1, min(limit, MAX_DELTA))
    rows = list(
        Annotation.objects.filter(document_id=document_id, seq__gt=since_seq).order_by("seq", "id")[: limit + 1]
    )
    more = len(rows) > limit
    if more:
        rows = rows[:limit]
        last_seq = rows[-1].seq
        rows += list(
            Annotation.objects.filter(document_id=document_id, seq=last_seq).exclude(pk__in=[r.id for r in rows])
        )
        more = Annotation.objects.filter(document_id=document_id, seq__gt=last_seq).exists()
    next_since = rows[-1].seq if more else max(change_seq, rows[-1].seq if rows else since_seq, since_seq)
    return AnnotationDelta(annotation_cards(rows), change_seq, next_since, more)


def text_filter(qs: QuerySet[Annotation], q: str) -> QuerySet[Annotation]:
    """Marks whose quote or comment match `q`: full text on PostgreSQL, every term as a substring elsewhere."""
    if not clean_query(q):
        return qs
    if connection.vendor == "postgresql":
        from django.contrib.postgres.search import SearchQuery

        prepared = prepare_query(q)
        return qs.filter(
            search_tsv=SearchQuery(prepared, config="english", search_type="websearch")
            | SearchQuery(prepared, config="simple", search_type="websearch")
        )
    for term in terms(q):
        qs = qs.filter(Q(quote_exact__icontains=term) | Q(comment__icontains=term))
    return qs
