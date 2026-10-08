"""
Quota as database facts, in the Notes pattern: every reservation is ONE conditional UPDATE,

    UPDATE recall_quotausage SET cards_active = cards_active + 1 WHERE user_id = :u AND cards_active <= :limit - 1

and zero rows updated means the quota is full. Two requests racing for the last slot cannot both pass, because the database
serialises the updates on the row. Never read-then-write. Releases clamp at zero. Reviewing is never limited.
"""

from __future__ import annotations

from django.db.models import F, Value
from django.db.models.functions import Greatest
from django.utils import timezone

from core.plans import plan_code_for

from ..domain.quota import FREE, Limits
from ..errors import QuotaExceeded
from ..models import RecallDeck, RecallItem, RecallQuotaPlan, RecallQuotaUsage


def limits_for(user_id) -> Limits:
    row = RecallQuotaPlan.objects.filter(pk=plan_code_for(user_id)).first()
    if row is None:  # a missing row must never mean "unlimited"
        return FREE
    return Limits(**{name: getattr(row, name) for name in Limits.names()})


def ensure_usage(user_id) -> None:
    RecallQuotaUsage.objects.bulk_create([RecallQuotaUsage(user_id=user_id)], ignore_conflicts=True)


def _exceeded(user_id, kind: str, used: int, limit: int) -> QuotaExceeded:
    return QuotaExceeded(extra={"kind": kind, "used": used, "limit": limit, "plan": plan_code_for(user_id)})


def _reserve(user_id, field: str, amount: int, limit: int, kind: str) -> None:
    ensure_usage(user_id)
    updated = RecallQuotaUsage.objects.filter(**{"user_id": user_id, f"{field}__lte": limit - amount}).update(
        **{field: F(field) + amount, "updated_at": timezone.now()}
    )
    if not updated:
        used = RecallQuotaUsage.objects.filter(pk=user_id).values_list(field, flat=True).first() or 0
        raise _exceeded(user_id, kind, used, limit)


def _release(user_id, field: str, amount: int) -> None:
    RecallQuotaUsage.objects.filter(pk=user_id).update(
        **{field: Greatest(F(field) - amount, Value(0)), "updated_at": timezone.now()}
    )


def reserve_cards(user_id, amount: int = 1) -> None:
    """Own cards (platform subscriptions do not count). An import reserves its whole size at once."""
    _reserve(user_id, "cards_active", amount, limits_for(user_id).max_cards, "cards")


def release_cards(user_id, amount: int = 1) -> None:
    _release(user_id, "cards_active", amount)


def reserve_deck(user_id) -> None:
    _reserve(user_id, "decks_active", 1, limits_for(user_id).max_decks, "decks")


def release_deck(user_id) -> None:
    _release(user_id, "decks_active", 1)


def reserve_deck_member(user_id, deck_id, amount: int = 1) -> None:
    """One more card in a student's own deck: a conditional UPDATE of the deck's counter against the per-deck limit."""
    limit = limits_for(user_id).max_cards_per_deck
    updated = RecallDeck.objects.filter(pk=deck_id, owner_user_id=user_id, card_count__lte=limit - amount).update(
        card_count=F("card_count") + amount, updated_at=timezone.now()
    )
    if not updated:
        used = RecallDeck.objects.filter(pk=deck_id, owner_user_id=user_id).values_list("card_count", flat=True).first()
        raise _exceeded(user_id, "cards_per_deck", used or 0, limit)


def release_deck_member(user_id, deck_id, amount: int = 1) -> None:
    RecallDeck.objects.filter(pk=deck_id, owner_user_id=user_id).update(
        card_count=Greatest(F("card_count") - amount, Value(0)), updated_at=timezone.now()
    )


def pack_size(user_id) -> int:
    return limits_for(user_id).pack_size


def reconcile(user_id) -> dict[str, int]:
    """Recompute the counters from the tables (the counters are a cache). Run by a support command, never on a request."""
    ensure_usage(user_id)
    cards = RecallItem.objects.filter(
        owner_user_id=user_id, ownership="user", status__in=["active", "archived"]
    ).count()
    decks = RecallDeck.objects.filter(owner_user_id=user_id, kind="user", status__in=["active", "archived"]).count()
    RecallQuotaUsage.objects.filter(pk=user_id).update(
        cards_active=cards, decks_active=decks, reconciled_at=timezone.now(), updated_at=timezone.now()
    )
    return {"cards_active": cards, "decks_active": decks}
