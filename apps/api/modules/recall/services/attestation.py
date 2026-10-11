"""
"These are my own words" (FR-F15-21, R2-W4). A card made from a selection of platform or third-party text (a highlight, a
solution, a mistake) is private (`shareable = false`). When she rewrites it in her own words she can say so: the item becomes
shareable and the time of the statement is kept (`shareable_attested_at`); she can take the statement back at any time. Each
change is written to the audit log (ids only, no text). Sharing itself is a later wave: today this only sets and reports the state
that Share will read. Idempotent in both directions.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import NotFound

from ..domain import attestation as rules
from ..errors import AttestationNotNeeded
from ..models import RecallAuditLog, RecallCard, RecallItem


@dataclass(frozen=True)
class Attestation:
    required: bool  # the card started private, so the statement is what makes it shareable
    attested: bool
    attested_at: datetime | None
    changed: bool


def set_own_words(user_id, card_id, *, own_words: bool, now: datetime | None = None) -> Attestation:
    """Make her card shareable (`own_words=True`) or private again. 404 for another student's card, 422 `attestation_not_needed`."""
    now = now or timezone.now()
    with transaction.atomic():
        probe = (
            RecallCard.objects.filter(pk=card_id, user_id=user_id)
            .exclude(status="deleted")
            .values_list("item_id", flat=True)
            .first()
        )
        if probe is None:
            raise NotFound("Card not found.")
        item = RecallItem.objects.select_for_update().get(pk=probe)
        if str(item.owner_user_id) != str(user_id) or not rules.required(item.ownership, item.origin):
            raise AttestationNotNeeded
        currently = item.shareable and item.shareable_attested_at is not None
        if currently == own_words:
            return Attestation(True, currently, item.shareable_attested_at, changed=False)
        item.shareable = own_words
        item.shareable_attested_at = now if own_words else None
        item.save(update_fields=["shareable", "shareable_attested_at", "updated_at"])
        RecallAuditLog.objects.create(
            actor_id=user_id,
            action="attest_own_words",
            target_kind="item",
            target_id=str(item.id),
            detail={"v": 1, "own_words": own_words, "origin": item.origin},
        )
        return Attestation(True, own_words, item.shareable_attested_at, changed=True)
