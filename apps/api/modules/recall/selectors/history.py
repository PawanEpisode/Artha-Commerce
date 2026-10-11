"""
Her history of updates (R2-W4): what moving to a newer deck version did to her, and what changed in one card. Pure reads of her
own rows. Text (the first line of a version) goes to the signed-in owner only and is never logged.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from rest_framework.exceptions import NotFound

from ..domain import decks as deck_domain
from ..models import RecallCard, RecallItemVersion, RecallScheduleEvent, RecallSubscription, RecallSubscriptionUpdate

HISTORY_LIMIT = 50
VERSIONS_LIMIT = 20
RESETS_LIMIT = 10
TEXT_MAX = 300


@dataclass(frozen=True)
class UpdateRow:
    id: UUID
    from_no: int
    to_no: int
    versions_skipped: int
    trigger: str
    applied_at: datetime
    summary: dict
    changelog_md: str


@dataclass(frozen=True)
class VersionRow:
    version_no: int
    change_kind: str
    change_note: str
    at: datetime | None
    text: str
    received: bool  # at or below the version her card carries
    current: bool


@dataclass(frozen=True)
class ResetRow:
    at: datetime
    reason: str


@dataclass(frozen=True)
class CardChanges:
    card_id: UUID
    item_id: UUID
    platform: bool
    versions: list[VersionRow]
    resets: list[ResetRow]
    waiting: int  # newer versions of the item she has not received (a pinned deck)


def update_history(user_id, subscription_id, *, limit: int = HISTORY_LIMIT) -> list[UpdateRow]:
    """The updates received on one subscription, newest first (404 for another student's)."""
    if not RecallSubscription.objects.filter(pk=subscription_id, user_id=user_id).exists():
        raise NotFound("Subscription not found.")
    rows = (
        RecallSubscriptionUpdate.objects.filter(user_id=user_id, subscription_id=subscription_id)
        .select_related("to_version")
        .order_by("-applied_at", "-to_no")[:limit]
    )
    return [
        UpdateRow(
            r.id, r.from_no, r.to_no, r.versions_skipped, r.trigger, r.applied_at, r.summary, r.to_version.changelog_md
        )
        for r in rows
    ]


def card_changes(user_id, card_id) -> CardChanges:
    """The versions of the card's item up to the live one, with the ones she has and a note of each time it came back for a re-check."""
    card = RecallCard.objects.select_related("item", "item_version").filter(pk=card_id, user_id=user_id).first()
    if card is None:
        raise NotFound("Card not found.")
    have = card.item_version.version_no
    versions = list(
        RecallItemVersion.objects.filter(item_id=card.item_id, state__in=("live", "superseded")).order_by(
            "-version_no"
        )[:VERSIONS_LIMIT]
    )
    rows = [
        VersionRow(
            v.version_no,
            v.change_kind,
            v.change_note,
            v.live_at,
            deck_domain.preview(v.plain_text, TEXT_MAX),
            v.version_no <= have,
            v.version_no == have,
        )
        for v in versions
    ]
    resets = [
        ResetRow(e.at, e.reason_code)
        for e in RecallScheduleEvent.objects.filter(user_id=user_id, card_id=card.id, kind="content_reset").order_by(
            "-at"
        )[:RESETS_LIMIT]
    ]
    return CardChanges(
        card.id,
        card.item_id,
        card.item.ownership == "platform",
        rows,
        resets,
        sum(1 for v in versions if v.version_no > have),
    )
