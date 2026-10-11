"""
Reads of platform decks for the student (PRD 9.3). Only ACTIVE platform decks with a LIVE version are visible: a draft, a
withdrawn deck or a deck without a published version does not exist for students. R1 shows "A newer version exists" as a count
(`newer_versions`) and nothing more.
"""

from __future__ import annotations

import base64
import json
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from django.db.models import Exists, OuterRef, Q

from ..adapters import coverage as coverage_adapter
from ..adapters import syllabus as syllabus_adapter
from ..domain import decks as domain
from ..errors import BadCursor, DeckNotFound
from ..models import RecallDeck, RecallDeckVersion, RecallDeckVersionItem, RecallSubscription
from .amendments import under_review_item_ids
from .cards import Page
from .updates import plan_for


@dataclass(frozen=True)
class SubscriptionView:
    id: UUID
    status: str
    version_no: int  # the deck version she has synced
    newer_versions: int  # published versions after hers
    subscribed_at: datetime
    min_importance: str
    follow_updates: bool = True
    update_available: bool = False  # a newer live version exists for an active subscription
    pending_changes: int = 0  # changes in the update that concern her cards (the banner's number)
    pending_version_no: int | None = None
    old_syllabus: bool = False  # the deck is for a scheme other than the one of her active enrolment


@dataclass(frozen=True)
class DeckView:
    id: UUID
    slug: str | None
    title: str
    description: str
    course_id: UUID | None
    level_id: UUID | None
    subject_key: str | None
    subject_name: str
    chapter_id: UUID | None
    chapter_name: str
    version_no: int
    item_count: int
    card_count: int
    tiers: dict
    published_at: datetime | None
    changelog_md: str
    subscription: SubscriptionView | None


@dataclass(frozen=True)
class DeckItemView:
    item_id: UUID
    kind: str
    importance: str
    position: int
    preview: str
    chapter_name: str
    under_review: bool = False  # the "Under review after amendment" ribbon


@dataclass(frozen=True)
class DeckDetail:
    deck: DeckView
    items: list[DeckItemView] = field(default_factory=list)


def _encode(title: str, pk: UUID) -> str:
    return base64.urlsafe_b64encode(json.dumps([title, str(pk)]).encode()).decode().rstrip("=")


def _decode(cursor: str) -> tuple[str, UUID]:
    try:
        raw = json.loads(base64.urlsafe_b64decode((cursor + "=" * (-len(cursor) % 4)).encode()))
        return str(raw[0]), UUID(raw[1])
    except (ValueError, TypeError, IndexError, UnicodeDecodeError) as exc:
        raise BadCursor from exc


def _visible():
    return RecallDeck.objects.filter(
        kind="platform", status="active", deleted_at__isnull=True, live_version__isnull=False
    ).select_related("live_version", "subject", "chapter")


def _old_syllabus(user_id, subs: list[RecallSubscription]) -> dict[UUID, bool]:
    """Per deck: is it written for another scheme than the one of her active enrolment (read from the deck's chapter)."""
    chapters = {s.deck_id: s.deck.chapter_id for s in subs if s.deck.chapter_id}
    active = coverage_adapter.active_scheme_id(user_id) if chapters else None
    if active is None:
        return {}
    refs = syllabus_adapter.chapter_refs(list(chapters.values()))
    return {d: (refs[c].scheme_id != active) for d, c in chapters.items() if c in refs}


def _subscriptions(user_id, deck_ids: Sequence[UUID]) -> dict[UUID, SubscriptionView]:
    subs = list(
        RecallSubscription.objects.filter(user_id=user_id, deck_id__in=list(deck_ids)).select_related(
            "synced_version", "pending_version", "deck__live_version"
        )
    )
    if not subs:
        return {}
    old = _old_syllabus(user_id, subs)
    out = {}
    for s in subs:
        count = RecallDeckVersion.objects.filter(
            deck_id=s.deck_id, state__in=("live", "superseded"), version_no__gt=s.synced_version.version_no
        ).count()
        plan = plan_for(s) if count and s.status == "active" else None
        out[s.deck_id] = SubscriptionView(
            id=s.id,
            status=s.status,
            version_no=s.synced_version.version_no,
            newer_versions=count,
            subscribed_at=s.subscribed_at,
            min_importance=s.min_importance,
            follow_updates=s.follow_updates,
            update_available=plan is not None,
            pending_changes=plan.summary["total"] if plan is not None else 0,
            pending_version_no=s.pending_version.version_no if s.pending_version_id else None,
            old_syllabus=old.get(s.deck_id, False),
        )
    return out


def _view(deck: RecallDeck, subscription: SubscriptionView | None) -> DeckView:
    v = deck.live_version
    return DeckView(
        id=deck.id,
        slug=deck.slug,
        title=deck.title,
        description=deck.description,
        course_id=deck.course_id,
        level_id=deck.level_id,
        subject_key=deck.subject.key if deck.subject_id else None,
        subject_name=deck.subject.name if deck.subject_id else "",
        chapter_id=deck.chapter_id,
        chapter_name=deck.chapter.name if deck.chapter_id else "",
        version_no=v.version_no,
        item_count=v.item_count,
        card_count=int(v.tier_counts.get("cards", 0)),
        tiers={t: int(v.tier_counts.get(t, 0)) for t in reversed(domain.IMPORTANCE_ORDER)},
        published_at=v.published_at,
        changelog_md=v.changelog_md,
        subscription=subscription,
    )


def library(
    user_id,
    *,
    course: str | None = None,
    level: str | None = None,
    subject_key: str | None = None,
    chapter_id: UUID | None = None,
    tier: str | None = None,
    cursor: str | None = None,
    limit: int | None = None,
) -> Page[DeckView]:
    qs = _visible()
    if course:
        qs = qs.filter(course__code=course)
    if level:
        qs = qs.filter(level__code=level)
    if subject_key:
        qs = qs.filter(subject__key=subject_key)
    if chapter_id:
        qs = qs.filter(chapter_id=chapter_id)
    if tier:
        qs = qs.filter(
            Exists(
                RecallDeckVersionItem.objects.filter(
                    deck_version_id=OuterRef("live_version_id"), item__importance=tier, item__status="active"
                )
            )
        )
    if cursor:
        title, last = _decode(cursor)
        qs = qs.filter(Q(title__gt=title) | Q(title=title, pk__gt=last))
    limit = max(1, min(limit or domain.LIBRARY_PAGE, domain.LIBRARY_PAGE_MAX))
    rows = list(qs.order_by("title", "pk")[: limit + 1])
    more = len(rows) > limit
    rows = rows[:limit]
    subs = _subscriptions(user_id, [d.id for d in rows])
    return Page([_view(d, subs.get(d.id)) for d in rows], _encode(rows[-1].title, rows[-1].pk) if more else None)


def deck_detail(user_id, deck_id: UUID) -> DeckDetail:
    """The live snapshot of a deck, or 404 `deck_not_found`. A student with an archived subscription still sees it."""
    deck = _visible().filter(pk=deck_id).first()
    if deck is None:
        raise DeckNotFound
    sub = _subscriptions(user_id, [deck.id]).get(deck.id)
    rows = list(
        RecallDeckVersionItem.objects.filter(deck_version_id=deck.live_version_id, item__status="active")
        .select_related("item", "item_version")
        .order_by("position", "item_id")
    )
    chapters = syllabus_adapter.chapter_refs([r.item.chapter_id for r in rows])
    flagged = under_review_item_ids([r.item_id for r in rows])
    items = [
        DeckItemView(
            item_id=r.item_id,
            kind=r.item.kind,
            importance=r.item.importance,
            position=r.position,
            preview=domain.preview(r.item_version.plain_text.split("\n", 1)[0]),
            chapter_name=chapters[r.item.chapter_id].name if r.item.chapter_id in chapters else "",
            under_review=r.item_id in flagged,
        )
        for r in rows
    ]
    return DeckDetail(_view(deck, sub), items)


def my_subscriptions(user_id) -> list[DeckView]:
    """Platform decks she is subscribed to (active first), for the "Subscribed" tab; a withdrawn deck drops out."""
    subs = list(RecallSubscription.objects.filter(user_id=user_id).values_list("deck_id", flat=True))
    if not subs:
        return []
    decks = list(_visible().filter(pk__in=subs).order_by("title", "pk"))
    views = _subscriptions(user_id, [d.id for d in decks])
    out = [_view(d, views.get(d.id)) for d in decks]
    out.sort(key=lambda v: (v.subscription.status != "active" if v.subscription else True, v.title))
    return out
