"""
"Needs a new chapter" (R2-W2, FR-F15-50): her own cards that wait for a chapter of the new scheme. Pure reads for the owner; the
label is the first line of her own card and is never logged.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from uuid import UUID

from ..adapters import syllabus as syllabus_adapter
from ..domain import decks as deck_domain
from ..models import RecallCard, RecallChapterRemap


@dataclass(frozen=True)
class RemapView:
    id: UUID
    relation: str
    label: str
    card_count: int
    from_chapter: object | None  # a syllabus ChapterRef (old scheme) or None
    candidates: list = field(default_factory=list)  # ChapterRefs she is offered first


@dataclass(frozen=True)
class RemapScreen:
    items: list[RemapView]
    chapters: list  # every chapter of the new scheme, for "pick any chapter"
    to_scheme_id: UUID | None


def pending_count(user_id) -> int:
    return RecallChapterRemap.objects.filter(user_id=user_id, status="pending").count()


def pending(user_id, *, limit: int = 200) -> RemapScreen:
    rows = list(
        RecallChapterRemap.objects.filter(user_id=user_id, status="pending")
        .select_related("item__live_version")
        .order_by("created_at", "id")[:limit]
    )
    if not rows:
        return RemapScreen([], [], None)
    counts = dict(
        Counter(
            RecallCard.objects.filter(user_id=user_id, item_id__in=[r.item_id for r in rows])
            .exclude(status="deleted")
            .values_list("item_id", flat=True)
        )
    )
    wanted = {r.from_chapter_id for r in rows if r.from_chapter_id}
    for r in rows:
        wanted.update(UUID(str(c)) for c in r.candidate_chapter_ids)
    refs = syllabus_adapter.chapter_refs(list(wanted))
    items = []
    for r in rows:
        version = r.item.live_version
        label = deck_domain.preview(version.plain_text.split("\n", 1)[0]) if version is not None else ""
        items.append(
            RemapView(
                r.id,
                r.relation,
                label,
                counts.get(r.item_id, 0),
                refs.get(r.from_chapter_id),
                [refs[UUID(str(c))] for c in r.candidate_chapter_ids if UUID(str(c)) in refs],
            )
        )
    scheme = Counter(r.to_scheme_id for r in rows).most_common(1)[0][0]
    return RemapScreen(items, syllabus_adapter.chapters_of_scheme(scheme), scheme)
