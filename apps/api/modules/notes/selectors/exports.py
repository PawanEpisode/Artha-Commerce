"""Reads for exports (ERD 2.10, 6.5): the job a student polls, the live marks a flattened PDF burns in, and the rows of the archive."""

from __future__ import annotations

import logging
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from django.db.models import Q
from django.utils import timezone

from modules.media import services as media
from modules.media.errors import NotReady, StorageUnavailable

from ..domain.export_options import ExportOptions
from ..models import Annotation, ExportJob, ItemTag, Note
from ._common import LinkView, NoteCard, cards, link_views

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ExportView:
    job: ExportJob
    status: str  # the job's status, except that a finished export past its retention reads as `expired` before the sweep runs
    download_url: str | None = None
    download_expires_at: datetime | None = None


def get_export(user_id, export_id) -> ExportView | None:
    """The student's own export (None for anyone else's). A signed link is issued on demand, only while the file is `done`."""
    job = ExportJob.objects.filter(pk=export_id, user_id=user_id).select_related("attachment").first()
    if job is None:
        return None
    status = job.status
    if status == "done" and job.expires_at is not None and job.expires_at <= timezone.now():
        status = "expired"
    if status != "done" or job.attachment_id is None:
        return ExportView(job, status)
    try:
        link = media.signed_url(user_id, job.attachment_id)
    except (
        NotReady,
        StorageUnavailable,
    ):  # a file that cannot be signed right now is simply not offered; the poll retries
        logger.warning("Export link could not be signed")
        return ExportView(job, status)
    return ExportView(job, status, link.url, link.expires_at)


def marks_for_export(user_id, document_id, options: ExportOptions) -> list[dict]:
    """
    Live marks of one document in page order, filtered by the export options, in one query on the `(document, page)` index:
    kinds, page selection, colours (a mark without a colour is kept: it has none to filter by) and tags (any of them).
    """
    qs = Annotation.objects.filter(
        user_id=user_id, document_id=document_id, deleted_at__isnull=True, kind__in=options.include
    )
    if options.pages is not None:
        qs = qs.filter(page__in=options.pages)
    if options.colors is not None:
        qs = qs.filter(Q(color__in=options.colors) | Q(color__isnull=True))
    if options.tags is not None:
        tagged = ItemTag.objects.filter(user_id=user_id, annotation__isnull=False, tag_id__in=options.tags)
        qs = qs.filter(pk__in=tagged.values("annotation_id"))
    return list(
        qs.order_by("page", "created_at", "id").values("page", "kind", "geometry", "color", "comment", "quote_exact")
    )


# --- The archive ---------------------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class MarkRow:
    mark: Annotation
    link: LinkView
    tags: tuple[str, ...]


def note_cards(user_id, *, limit: int, batch: int = 200) -> Iterator[list[NoteCard]]:
    """The student's live notes, oldest first, at most `limit` (their plan's note count), in batches with tags and links."""
    qs = Note.objects.filter(user_id=user_id, deleted_at__isnull=True).order_by("created_at", "id")[:limit]
    chunk: list[Note] = []
    for note in qs.iterator(chunk_size=batch):
        chunk.append(note)
        if len(chunk) == batch:
            yield cards(chunk)
            chunk = []
    if chunk:
        yield cards(chunk)


def mark_rows(user_id, document_id, kinds: Sequence[str], *, batch: int = 500) -> Iterator[list[MarkRow]]:
    """Live marks of the given kinds of one document in page order, in batches with their syllabus link and tag names."""
    qs = Annotation.objects.filter(
        user_id=user_id, document_id=document_id, deleted_at__isnull=True, kind__in=list(kinds)
    ).order_by("page", "created_at", "id")
    chunk: list[Annotation] = []
    for mark in qs.iterator(chunk_size=batch):
        chunk.append(mark)
        if len(chunk) == batch:
            yield _mark_batch(chunk)
            chunk = []
    if chunk:
        yield _mark_batch(chunk)


def _mark_batch(marks: list[Annotation]) -> list[MarkRow]:
    tag_names: dict[Any, list[str]] = {}
    for item in (
        ItemTag.objects.filter(annotation_id__in=[m.id for m in marks]).select_related("tag").order_by("tag__name")
    ):
        tag_names.setdefault(item.annotation_id, []).append(item.tag.name)
    links = link_views(marks)
    return [MarkRow(m, link, tuple(tag_names.get(m.id, ()))) for m, link in zip(marks, links, strict=True)]
