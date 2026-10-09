"""
Card reads (PRD 9.2). `get_card` answers None for another student's card (the view turns that into 404), `list_cards` is a
keyset-paginated browse with the filters of the contract, and `card_for_source` / `cards_for_source` serve the Notes provider.
"""

from __future__ import annotations

import base64
import json
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Generic, TypeVar
from uuid import UUID

from django.db.models import Exists, OuterRef, Q, QuerySet

from ..adapters import syllabus as syllabus_adapter
from ..domain import cards as domain
from ..errors import BadCursor
from ..models import RecallCard, RecallDeckItem, RecallItem, RecallReviewLog
from ..vocab import IMPORTANCE_INT

MAX_LIMIT = 100
DEFAULT_LIMIT = 30
T = TypeVar("T")
SORTS = {"newest": ("created_at", True), "oldest": ("created_at", False), "updated": ("updated_at", True)}
STATES = ("new", "learning", "review", "suspended", "tricky", "recheck")


@dataclass(frozen=True)
class Page(Generic[T]):  # noqa: UP046 - `class Page[T]` is 3.12 syntax
    items: list[T]
    next_cursor: str | None = None


@dataclass(frozen=True)
class CardView:
    card: RecallCard
    item: RecallItem
    fields: dict
    front_md: str
    back_md: str
    chapter: Any = None  # a syllabus ChapterRef, or None when Unsorted or no longer visible
    deck_ids: tuple[UUID, ...] = ()


@dataclass(frozen=True)
class CardFilter:
    subject_key: str | None = None
    chapter_id: UUID | None = None
    kind: str | None = None
    tier: str | None = None
    state: str | None = None
    deck_id: UUID | None = None
    q: str = ""
    status: str | None = None  # default: everything not deleted
    sort: str = "newest"


def render_card(item: RecallItem, fields: dict, ordinal: int) -> tuple[str, str]:
    return domain.render(item.kind, fields, ordinal)


def _views(cards: Sequence[RecallCard]) -> list[CardView]:
    refs = syllabus_adapter.chapter_refs(c.chapter_id for c in cards)
    decks: dict[UUID, list[UUID]] = {}
    for item_id, deck_id in RecallDeckItem.objects.filter(item_id__in={c.item_id for c in cards}).values_list(
        "item_id", "deck_id"
    ):
        decks.setdefault(item_id, []).append(deck_id)
    out = []
    for card in cards:
        fields = card.item_version.fields
        front, back = render_card(card.item, fields, card.ordinal)
        out.append(
            CardView(
                card, card.item, fields, front, back, refs.get(card.chapter_id), tuple(decks.get(card.item_id, ()))
            )
        )
    return out


def _base(user_id) -> QuerySet[RecallCard]:
    return RecallCard.objects.select_related("item", "item_version").filter(user_id=user_id)


def get_card(user_id, card_id) -> CardView | None:
    card = _base(user_id).filter(pk=card_id).first()
    return _views([card])[0] if card else None


def _state_q(state: str) -> Q:
    return {
        "new": Q(state=0, status="active"),
        "learning": Q(state__in=[1, 3], status="active"),
        "review": Q(state=2, status="active"),
        "suspended": Q(status="suspended"),
        "tricky": Q(leech=True),
        "recheck": Q(needs_recheck=True),
    }[state]


def _filtered(user_id, f: CardFilter) -> QuerySet[RecallCard]:
    qs = _base(user_id)
    qs = qs.filter(status=f.status) if f.status else qs.exclude(status="deleted")
    if f.subject_key:
        qs = qs.filter(subject_key=f.subject_key)
    if f.chapter_id:
        qs = qs.filter(chapter_id=f.chapter_id)
    if f.kind:
        qs = qs.filter(item__kind=f.kind)
    if f.tier:
        qs = qs.filter(importance=IMPORTANCE_INT[f.tier])
    if f.state:
        qs = qs.filter(_state_q(f.state))
    if f.deck_id:
        members = RecallDeckItem.objects.filter(
            deck_id=f.deck_id, deck__owner_user_id=user_id, item_id=OuterRef("item_id")
        )
        qs = qs.filter(Exists(members))
    if f.q.strip():
        qs = qs.filter(item__search_text__icontains=f.q.strip())
    return qs


def _encode(parts: Sequence[Any]) -> str:
    raw = json.dumps([p.isoformat() if isinstance(p, datetime) else str(p) for p in parts])
    return base64.urlsafe_b64encode(raw.encode()).decode().rstrip("=")


def _decode(cursor: str) -> tuple[datetime, UUID]:
    try:
        parts = json.loads(base64.urlsafe_b64decode((cursor + "=" * (-len(cursor) % 4)).encode()))
        return datetime.fromisoformat(parts[0]), UUID(parts[1])
    except (ValueError, TypeError, IndexError, UnicodeDecodeError) as exc:
        raise BadCursor from exc


def list_cards(
    user_id, f: CardFilter | None = None, *, cursor: str | None = None, limit: int | None = None
) -> Page[CardView]:
    f = f or CardFilter()
    column, newest_first = SORTS.get(f.sort, SORTS["newest"])
    limit = max(1, min(limit or DEFAULT_LIMIT, MAX_LIMIT))
    qs = _filtered(user_id, f)
    if cursor:
        at, last_id = _decode(cursor)
        before, same = (
            ({f"{column}__lt": at}, {f"{column}": at, "pk__lt": last_id})
            if newest_first
            else ({f"{column}__gt": at}, {f"{column}": at, "pk__gt": last_id})
        )
        qs = qs.filter(Q(**before) | Q(**same))
    sign = "-" if newest_first else ""
    rows = list(qs.order_by(f"{sign}{column}", f"{sign}pk")[: limit + 1])
    more = len(rows) > limit
    rows = rows[:limit]
    return Page(_views(rows), _encode([getattr(rows[-1], column), rows[-1].pk]) if more else None)


def card_for_source(user_id, module: str, ref_id, origin_kind: str) -> UUID | None:
    """The first card of the student's item made from this source object and port kind, if any."""
    item = RecallItem.objects.filter(
        owner_user_id=user_id,
        origin_module=module,
        origin_ref=str(ref_id),
        origin_kind=origin_kind,
        status__in=["active", "archived"],
    ).first()
    if item is None:
        return None
    return (
        RecallCard.objects.filter(item=item, user_id=user_id)
        .exclude(status="deleted")
        .order_by("ordinal")
        .values_list("id", flat=True)
        .first()
    )


def cards_for_source(user_id, module: str | None, ref_ids: Sequence[UUID]) -> dict[UUID, UUID]:
    """`{source id: card id}` for the student's active cards made from those source objects (the first card per source)."""
    if not ref_ids:
        return {}
    wanted = {str(r): r for r in ref_ids}
    qs = RecallCard.objects.filter(
        user_id=user_id, item__origin_ref__in=list(wanted), item__status__in=["active", "archived"]
    )
    if module:
        qs = qs.filter(item__origin_module=module)
    rows = qs.exclude(status="deleted").order_by("created_at", "ordinal").values_list("item__origin_ref", "id")
    out: dict[UUID, UUID] = {}
    for ref, card_id in rows:
        out.setdefault(wanted[ref], card_id)
    return out


HISTORY_LIMIT = 50


def card_history(user_id, card_id, limit: int = HISTORY_LIMIT) -> list[RecallReviewLog]:
    """The latest reviews of one of her cards, newest first. Undone reviews are left out. Empty for another student's card."""
    undone = RecallReviewLog.objects.filter(user_id=user_id, kind="undo").values("voids_id")
    return list(
        RecallReviewLog.objects.filter(user_id=user_id, card_id=card_id, kind="review")
        .exclude(id__in=undone)
        .order_by("-reviewed_at", "-id")[: min(limit, HISTORY_LIMIT)]
    )
