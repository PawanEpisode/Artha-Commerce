"""
Scheme switch for her OWN cards (R2-W2, FR-F15-50). When her active enrolment moves to a new scheme (F-02 announces
`enrollment_scheme_changed`), a job moves the cards she wrote through the chapter map (`domain/remap.py` has the rules):
same, renamed and merged chapters follow their one target at once, a split offers both targets, anything else waits in
"Needs a new chapter" for her choice. Platform items keep their platform chapter; her subscription to a deck of the old scheme is
flagged by the deck read ("Deck is for the old syllabus"). A card is never lost, the review log is never touched, and running the job
twice changes nothing.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from django.db import transaction
from django.db.models import F
from django.utils import timezone
from rest_framework.exceptions import NotFound

from core import jobs as core_jobs

from ..adapters import syllabus as syllabus_adapter
from ..domain import remap as domain
from ..errors import UnknownChapter
from ..models import RecallCard, RecallChapterRemap, RecallItem

logger = logging.getLogger(__name__)

JOB_SCHEME_CHANGED = "recall.scheme_changed"
BATCH = 500


@dataclass
class RemapResult:
    moved: int = 0  # items that followed the map at once
    waiting: int = 0  # items waiting for her choice
    unchanged: int = 0  # items already in the new scheme


def queue_student(user_id, to_scheme_id) -> None:
    """The scheme changed: move her cards soon. Merged with a job already waiting for the same student and scheme."""
    core_jobs.enqueue(
        JOB_SCHEME_CHANGED,
        {"user_id": str(user_id), "to_scheme_id": str(to_scheme_id)},
        dedupe_key=f"{JOB_SCHEME_CHANGED}:{user_id}:{to_scheme_id}",
    )


def _apply_chapter(user_id, item_ids: list, chapter_id, link: dict, now: datetime) -> None:
    RecallItem.objects.filter(pk__in=item_ids, owner_user_id=user_id).update(**link, updated_at=now)
    RecallCard.objects.filter(user_id=user_id, item_id__in=item_ids).update(
        chapter_id=chapter_id, subject_key=link["subject_key"], rev=F("rev") + 1, updated_at=now
    )


def remap_student(user_id, to_scheme_id, *, now: datetime | None = None) -> RemapResult:
    """Move her own cards to the new scheme, in batches. Idempotent."""
    now = now or timezone.now()
    refs = syllabus_adapter.chapters_of_scheme(to_scheme_id)
    result = RemapResult()
    if not refs:
        return result
    level_id = refs[0].level_id
    in_scheme = {r.id for r in refs}
    links: dict[UUID, dict] = {}
    after = None
    while True:
        qs = (
            RecallItem.objects.filter(
                ownership="user", owner_user_id=user_id, level_id=level_id, chapter_id__isnull=False
            )
            .exclude(status="deleted")
            .order_by("id")
        )
        if after is not None:
            qs = qs.filter(id__gt=after)
        batch = list(qs.values_list("id", "chapter_id", "scheme_id")[:BATCH])
        if not batch:
            return result
        after = batch[-1][0]
        todo = [(i, c) for i, c, s in batch if s != to_scheme_id and c not in in_scheme]
        result.unchanged += len(batch) - len(todo)
        by_chapter: dict[UUID, list[UUID]] = defaultdict(list)
        for item_id, chapter_id in todo:
            by_chapter[chapter_id].append(item_id)
        rows = defaultdict(list)
        for m in syllabus_adapter.chapter_maps_from(by_chapter, to_scheme_id):
            rows[m.from_chapter_id].append(domain.MapRow(str(m.to_chapter_id), m.relation, m.needs_review))
        with transaction.atomic():
            for chapter_id, item_ids in by_chapter.items():
                decision = domain.decide(rows.get(chapter_id, []))
                if decision.action == domain.MAP:
                    target = UUID(decision.to_chapter_id)
                    if target not in links:
                        links[target] = syllabus_adapter.link_columns(target)
                    _apply_chapter(user_id, item_ids, target, links[target], now)
                    RecallChapterRemap.objects.filter(user_id=user_id, item_id__in=item_ids, status="pending").update(
                        status="resolved", to_chapter_id=target, resolved_at=now, updated_at=now
                    )
                    result.moved += len(item_ids)
                    continue
                existing = {
                    r.item_id: r for r in RecallChapterRemap.objects.filter(user_id=user_id, item_id__in=item_ids)
                }
                fresh = []
                for item_id in item_ids:
                    row = existing.get(item_id)
                    if row is None:
                        fresh.append(
                            RecallChapterRemap(
                                user_id=user_id, item_id=item_id, from_chapter_id=chapter_id, to_scheme_id=to_scheme_id,
                                relation=decision.relation, candidate_chapter_ids=list(decision.candidates),
                            )
                        )  # fmt: skip
                    elif row.status == "pending" and row.to_scheme_id != to_scheme_id:
                        row.to_scheme_id, row.relation = to_scheme_id, decision.relation
                        row.candidate_chapter_ids = list(decision.candidates)
                        row.save(update_fields=["to_scheme_id", "relation", "candidate_chapter_ids", "updated_at"])
                RecallChapterRemap.objects.bulk_create(fresh)
                result.waiting += len(item_ids)
        if len(batch) < BATCH:
            return result


def choose_chapter(user_id, remap_id, chapter_id, *, now: datetime | None = None) -> RecallChapterRemap:
    """She picks a chapter of the new scheme for a card waiting in "Needs a new chapter". Safe to repeat; 422 for a chapter of another scheme."""
    now = now or timezone.now()
    with transaction.atomic():
        row = RecallChapterRemap.objects.select_for_update(of=("self",)).filter(pk=remap_id, user_id=user_id).first()
        if row is None:
            raise NotFound("Not found.")
        ref = syllabus_adapter.chapter_refs([chapter_id]).get(chapter_id)
        if ref is None or ref.scheme_id != row.to_scheme_id:
            raise UnknownChapter("Pick a chapter of your current syllabus.")
        link = syllabus_adapter.link_columns(chapter_id)
        _apply_chapter(user_id, [row.item_id], chapter_id, link, now)
        row.status, row.to_chapter_id, row.resolved_at = "resolved", chapter_id, now
        row.save(update_fields=["status", "to_chapter_id", "resolved_at", "updated_at"])
        return row
