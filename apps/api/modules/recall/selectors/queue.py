"""
The queue (PRD 9.1, ERD Q-1 and Q-3): which cards to study next, rendered, with the four interval previews. Pure reads; the
order comes from `domain.scheduling.plan_queue`. Quick revision and cram are R2 and answer 422 `not_in_this_release`.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import timedelta
from uuid import UUID

from django.db.models import Exists, OuterRef

from ..adapters import syllabus as syllabus_adapter
from ..domain import limits as lim
from ..domain.fsrs6 import MemoryState, Preview, preview
from ..domain.scheduling import CardView, Limits, Queue, plan_queue, review_ahead
from ..errors import NotInThisRelease
from ..models import RecallCard, RecallDeckItem
from .cards import render_card
from .study import Study

SOURCES = ("today", "chapter", "deck", "forgotten", "quick", "catchup", "cram", "review_ahead")
MAX_LIMIT = 50
NEW_POOL_CAP = 300


@dataclass(frozen=True)
class QueueCard:
    card: RecallCard
    front_md: str
    back_md: str
    chapter: object
    previews: dict[int, Preview]
    badges: tuple[str, ...]


@dataclass(frozen=True)
class QueueFilters:
    chapter_id: UUID | None = None
    deck_id: UUID | None = None
    kind: str | None = None
    tier: int | None = None  # importance 0, 1 or 2


NO_FILTERS = QueueFilters()


def _active(study: Study):
    return RecallCard.objects.filter(user_id=study.user_id, status="active", deleted_at__isnull=True).exclude(
        buried_until__gt=study.now
    )


def _apply(qs, f: QueueFilters, user_id):
    if f.chapter_id:
        qs = qs.filter(chapter_id=f.chapter_id)
    if f.kind:
        qs = qs.filter(item__kind=f.kind)
    if f.tier is not None:
        qs = qs.filter(importance=f.tier)
    if f.deck_id:
        members = RecallDeckItem.objects.filter(
            deck_id=f.deck_id, deck__owner_user_id=user_id, item_id=OuterRef("item_id")
        )
        qs = qs.filter(Exists(members))
    return qs


COLUMNS = (
    "id",
    "subject_key",
    "importance",
    "state",
    "stability",
    "last_review_at",
    "due_at",
    "created_at",
    "item__kind",
)


def _view(row: tuple, interleave: bool) -> CardView:
    id_, subject, importance, state, stability, last, due, created, _kind = row
    return CardView(str(id_), (subject or "") if interleave else "", importance, state, stability, last, due, created)


def candidates(
    study: Study,
    f: QueueFilters = NO_FILTERS,
    *,
    new_room: int | None = None,
    learning_ahead: timedelta = timedelta(0),
):
    """Due learning and review cards plus the new cards that fit the allowance: two queries, whatever the library's size."""
    due = list(
        _apply(
            _active(study).filter(state__gt=0, due_at__lte=study.day_end + learning_ahead),
            f,
            study.user_id,
        ).values_list(*COLUMNS)
    )
    room = new_room if new_room is not None else max(study.settings.new_per_day - study.new_done, 0)
    new: list[tuple] = []
    if room > 0:
        new = list(
            _apply(_active(study).filter(state=0), f, study.user_id)
            .order_by("-importance", "created_at", "id")
            .values_list(*COLUMNS)[: min(room, NEW_POOL_CAP)]
        )
    return due, new


def limits_of(study: Study, extra: int = 0) -> Limits:
    """The daily limits; `extra` is "Do 20 more": reviews allowed beyond the maximum (the new-card allowance is not raised)."""
    s = study.settings
    return Limits(s.new_per_day, s.reviews_per_day + max(extra, 0), study.new_done, study.reviews_done)


def plan_today(study: Study, f: QueueFilters = NO_FILTERS, extra: int = 0) -> tuple[Queue, dict[str, tuple]]:
    """The study day's plan and the rows behind it. A vacation or an exhausted limit gives an empty plan, not an error."""
    due, new = candidates(study, f)
    limits = limits_of(study, extra)
    rows = {str(r[0]): r for r in [*due, *new]}
    interleave = study.settings.interleave
    views = [_view(r, interleave) for r in rows.values()]
    s = study.settings
    queue = plan_queue(views, study.now, limits, study.weights[20], mode=s.catchup_mode, day_end=study.day_end)
    if queue.catchup.active and not s.pause_new_in_catchup:
        normal = plan_queue(views, study.now, limits, study.weights[20], mode="off", day_end=study.day_end)
        added = tuple(i for i in normal.ids if i not in queue.ids and rows[i][3] == 0)
        queue = Queue(queue.ids + added, queue.learning, queue.reviews, queue.new + len(added), queue.catchup)
    if study.vacation:
        queue = Queue((), 0, 0, 0, queue.catchup)
    return queue, rows


def _badges(card: RecallCard) -> tuple[str, ...]:
    out = []
    if card.leech:
        out.append("tricky")
    if card.needs_recheck:
        out.append("amendment" if card.recheck_reason == "amendment" else "updated")
    if card.state == 0:
        out.append("new")
    return tuple(out)


def memory_of(card: RecallCard) -> MemoryState:
    return MemoryState(
        card.state,
        card.step,
        card.stability,
        card.difficulty,
        card.last_review_at,
        card.reps,
        card.lapses,
        card.last_lapse_at,
    )


def render_cards(study: Study, ids: Sequence[str]) -> list[QueueCard]:
    """Content and previews for these cards in this order: one query for the rows, one for the chapters."""
    cards = {
        str(c.id): c
        for c in RecallCard.objects.select_related("item", "item_version").filter(
            user_id=study.user_id, id__in=list(ids)
        )
    }
    ordered = [cards[i] for i in ids if i in cards]
    chapters = syllabus_adapter.chapter_refs(c.chapter_id for c in ordered)
    out = []
    for c in ordered:
        front, back = render_card(c.item, c.item_version.fields, c.ordinal)
        out.append(
            QueueCard(
                c,
                front,
                back,
                chapters.get(c.chapter_id),
                preview(memory_of(c), study.now, study.weights, study.cfg, card_id=c.id),
                _badges(c),
            )
        )
    return out


def build_queue(
    study: Study,
    source: str,
    *,
    limit: int = 20,
    filters: QueueFilters = NO_FILTERS,
    exclude: Sequence[str] = (),
    forgotten_ids: Sequence[str] = (),
    extra: int = 0,
) -> list[QueueCard]:
    if source in ("quick", "cram"):
        raise NotInThisRelease
    limit = max(1, min(limit, MAX_LIMIT))
    skip = set(exclude)
    if source == "today":
        ids, _ = plan_today(study, filters, extra)
        order = list(ids.ids)
    elif source == "catchup":
        due, _new = candidates(study, filters, new_room=0)
        views = [_view(r, study.settings.interleave) for r in due]
        order = list(
            plan_queue(views, study.now, limits_of(study), study.weights[20], mode="on", day_end=study.day_end).ids
        )
    elif source in ("chapter", "deck"):
        due, new = candidates(study, filters, new_room=NEW_POOL_CAP)
        views = [_view(r, study.settings.interleave) for r in due]
        big = Limits(study.settings.new_per_day, lim.OFFLINE_EVENT_CAP, 0, 0)
        ordered = plan_queue(views, study.now, big, study.weights[20], mode="off", day_end=study.day_end)
        order = list(ordered.ids) + [str(r[0]) for r in new]
    elif source == "forgotten":
        order = list(forgotten_ids)
    else:  # review_ahead
        rows = _apply(_active(study).filter(state=2, due_at__gt=study.now), filters, study.user_id).values_list(
            *COLUMNS
        )
        order = list(review_ahead([_view(r, True) for r in rows], study.now, study.weights[20]))
    return render_cards(study, [i for i in order if i not in skip][:limit])
