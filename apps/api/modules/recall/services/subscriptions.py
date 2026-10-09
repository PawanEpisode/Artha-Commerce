"""
Subscribing to a platform deck (FR-F15-46, FR-F15-51, ERD 3.6), release 1.

Copy-on-subscribe: the student's own `RecallCard` rows are created from the live deck version in ONE transaction (the text is
referenced through `item_version_id`, never copied). A per-(student, deck) advisory lock serialises double taps and two
devices, and the unique `(user, deck)` subscription makes the call idempotent. A deck of more than 500 cards is refused, never
half copied. Platform cards do not count against the quota (only her own cards do).

R1 has no pinned subscribers, no follow-updates and no diffs (R2): a subscription is created at the live version and stays on
the cards it copied; the library shows "A newer version exists" as a count only.

Unsubscribe archives her cards for the deck and keeps every bit of progress; resubscribe (or subscribing again) brings the
same cards back with their intervals. A card whose item is also in another active subscription stays active.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from django.db import connection, transaction
from django.db.models import F
from django.utils import timezone
from rest_framework.exceptions import NotFound

from .. import registry
from ..domain import decks as domain
from ..domain import limits as lim
from ..errors import DeckNotFound, DeckTooLarge
from ..models import (
    RecallCard,
    RecallDeck,
    RecallDeckVersionItem,
    RecallSubscription,
)
from ..vocab import IMPORTANCE_INT
from .cards import _default_params


@dataclass(frozen=True)
class SubscribeResult:
    subscription: RecallSubscription
    created: bool  # False when she was already subscribed (a double tap), True for a first subscribe or a resubscribe
    cards_created: int
    cards_restored: int


def _lock(user_id, deck_id) -> None:
    """Advisory lock for this student and deck until the transaction ends (PostgreSQL; SQLite has a single writer)."""
    if connection.vendor == "postgresql":
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", [f"recall.subscribe:{user_id}:{deck_id}"])


def _live_rows(deck: RecallDeck, min_importance: str) -> list[RecallDeckVersionItem]:
    floor = domain.IMPORTANCE_ORDER.index(min_importance)
    tiers = [t for i, t in enumerate(domain.IMPORTANCE_ORDER) if i >= floor]
    return list(
        RecallDeckVersionItem.objects.filter(
            deck_version_id=deck.live_version_id, item__status="active", item__importance__in=tiers
        )
        .select_related("item", "item_version")
        .order_by("position", "item_id")
    )


def _faces(row: RecallDeckVersionItem) -> list[int]:
    spec = registry.get_kind(row.item.kind)
    return spec.ordinals({k: v for k, v in row.item_version.fields.items() if k != "v"})


def _materialise(user_id, subscription: RecallSubscription, rows: list[RecallDeckVersionItem]) -> tuple[int, int]:
    """Create the missing cards and bring her archived ones back (progress untouched). Returns (created, restored)."""
    now = timezone.now()
    wanted = {(r.item_id, o): r for r in rows for o in _faces(r)}
    have = {
        (c.item_id, c.ordinal): c
        for c in RecallCard.objects.filter(user_id=user_id, item_id__in={i for i, _ in wanted})
    }
    params = _default_params()
    fresh = [
        RecallCard(
            user_id=user_id,
            item_id=item_id,
            ordinal=ordinal,
            subscription=subscription,
            item_version_id=row.item_version_id,
            chapter_id=row.item.chapter_id,
            subject_key=row.item.subject_key,
            importance=IMPORTANCE_INT[row.item.importance],
            scheduler_version=lim.SCHEDULER_VERSION,
            params=params,
        )
        for (item_id, ordinal), row in wanted.items()
        if (item_id, ordinal) not in have
    ]
    RecallCard.objects.bulk_create(fresh)
    back = [c.pk for key, c in have.items() if key in wanted and c.status == "archived"]
    if back:
        RecallCard.objects.filter(pk__in=back).update(
            status="active", subscription=subscription, rev=F("rev") + 1, updated_at=now
        )
    return len(fresh), len(back)


def subscribe(
    user_id,
    deck_id: UUID,
    *,
    follow_updates: bool = True,
    unlock_mode: str = "with_coverage",
    min_importance: str = "bullet",
) -> SubscribeResult:
    """
    Idempotent. 404 `deck_not_found` unless the deck is an active platform deck with a live version; 422 `deck_too_large`
    over 500 cards. `follow_updates` and `unlock_mode` are stored for R2 and have no effect in R1.
    """
    with transaction.atomic():
        _lock(user_id, deck_id)
        deck = RecallDeck.objects.filter(
            pk=deck_id, kind="platform", status="active", live_version__isnull=False, deleted_at__isnull=True
        ).first()
        if deck is None:
            raise DeckNotFound
        existing = RecallSubscription.objects.select_for_update().filter(user_id=user_id, deck=deck).first()
        if existing is not None and existing.status == "active":
            return SubscribeResult(existing, False, 0, 0)
        if existing is not None:
            return _reactivate(user_id, existing, deck)
        rows = _live_rows(deck, min_importance)
        total = sum(len(_faces(r)) for r in rows)
        if total > domain.SUBSCRIBE_MAX_CARDS:
            raise DeckTooLarge(extra={"cards": total, "limit": domain.SUBSCRIBE_MAX_CARDS})
        subscription = RecallSubscription.objects.create(
            user_id=user_id,
            deck=deck,
            pinned_version_id=deck.live_version_id,
            synced_version_id=deck.live_version_id,
            follow_updates=follow_updates,
            unlock_mode=unlock_mode,
            min_importance=min_importance,
            last_sync_at=timezone.now(),
        )
        created, restored = _materialise(user_id, subscription, rows)
        return SubscribeResult(subscription, True, created, restored)


def _reactivate(user_id, subscription: RecallSubscription, deck: RecallDeck) -> SubscribeResult:
    """Resubscribe: her archived cards for this deck come back as they were; nothing new is added (that is R2's sync)."""
    now = timezone.now()
    subscription.status, subscription.archived_at = "active", None
    subscription.save(update_fields=["status", "archived_at"])
    owned = RecallCard.objects.filter(user_id=user_id, subscription=subscription, status="archived")
    restored = owned.update(status="active", rev=F("rev") + 1, updated_at=now)
    # Items that are in this deck and that she holds from an earlier unsubscribe of another deck come back too.
    rows = _live_rows(deck, subscription.min_importance)
    others = RecallCard.objects.filter(
        user_id=user_id, item_id__in=[r.item_id for r in rows], status="archived"
    ).exclude(subscription=subscription)
    ids = list(others.values_list("pk", flat=True))
    if ids:
        restored += RecallCard.objects.filter(pk__in=ids).update(
            status="active", subscription=subscription, rev=F("rev") + 1, updated_at=now
        )
    return SubscribeResult(subscription, True, 0, restored)


def _own(user_id, subscription_id) -> RecallSubscription:
    sub = RecallSubscription.objects.select_for_update(of=("self",)).filter(pk=subscription_id, user_id=user_id).first()
    if sub is None:
        raise NotFound("Subscription not found.")
    return sub


def unsubscribe(user_id, subscription_id: UUID) -> RecallSubscription:
    """Archive her cards for the deck (progress kept). Idempotent. Cards also in another active subscription stay active."""
    now = timezone.now()
    with transaction.atomic():
        sub = _own(user_id, subscription_id)
        _lock(user_id, sub.deck_id)
        if sub.status == "archived":
            return sub
        sub.status, sub.archived_at = "archived", now
        sub.save(update_fields=["status", "archived_at"])
        cards = RecallCard.objects.filter(user_id=user_id, subscription=sub).exclude(status__in=("archived", "deleted"))
        elsewhere = _items_in_other_active_subscriptions(user_id, sub)
        by_sub: dict = {}
        for item_id, other_id in elsewhere.items():
            by_sub.setdefault(other_id, []).append(item_id)
        for other_id, item_ids in by_sub.items():
            cards.filter(item_id__in=item_ids).update(subscription_id=other_id, updated_at=now)
        cards.exclude(item_id__in=list(elsewhere)).update(status="archived", rev=F("rev") + 1, updated_at=now)
        return sub


def _items_in_other_active_subscriptions(user_id, sub: RecallSubscription) -> dict:
    """item id -> the other active subscription that still contains it (one of them when there are several)."""
    out: dict = {}
    others = RecallSubscription.objects.filter(user_id=user_id, status="active").exclude(pk=sub.pk)
    for other in others:
        for item_id in RecallDeckVersionItem.objects.filter(
            deck_version_id=other.synced_version_id, item__status="active"
        ).values_list("item_id", flat=True):
            out.setdefault(item_id, other.pk)
    return out


def resubscribe(user_id, subscription_id: UUID) -> SubscribeResult:
    """Bring an archived subscription back with her progress (idempotent: an active one answers `created=False`)."""
    with transaction.atomic():
        sub = _own(user_id, subscription_id)
        _lock(user_id, sub.deck_id)
        if sub.status == "active":
            return SubscribeResult(sub, False, 0, 0)
        deck = RecallDeck.objects.filter(
            pk=sub.deck_id, kind="platform", status="active", deleted_at__isnull=True
        ).first()
        if deck is None or not deck.live_version_id:
            raise DeckNotFound
        return _reactivate(user_id, sub, deck)
