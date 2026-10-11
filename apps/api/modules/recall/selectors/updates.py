"""
Update reads for a subscription (R2-W2, FR-F15-47): what moving her from the deck version she has synced to the live one would
do. The plan is the same one the sync service applies (`plan_for`), so the preview a pinned student reads is the work Apply
does. Pure reads. Labels are the first line of the item's own text and go to the signed-in owner only; nothing here is logged.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

from rest_framework.exceptions import NotFound

from ..domain import decks as deck_domain
from ..domain import sync as domain
from ..models import (
    RecallCard,
    RecallDeckVersion,
    RecallDeckVersionItem,
    RecallItemVersion,
    RecallSubscription,
)


@dataclass(frozen=True)
class UpdatePlan:
    subscription: RecallSubscription
    target: RecallDeckVersion
    from_no: int
    versions_skipped: int  # published versions between hers and the target (not counting the target)
    changes: dict[str, str]  # item id -> change, only what concerns her cards
    summary: dict
    importance: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class PreviewItem:
    item_id: UUID
    kind: str
    label: str
    importance: str


@dataclass(frozen=True)
class UpdatePreview:
    subscription: RecallSubscription
    available: bool
    from_no: int
    to_no: int
    versions_skipped: int
    changelog_md: str
    summary: dict
    items: dict[str, list[PreviewItem]]
    more: dict[str, int]
    returning_today: int  # of her cards that come back for re-check at once


def _snapshot(version_id, *, active_only: bool) -> dict[str, str]:
    qs = RecallDeckVersionItem.objects.filter(deck_version_id=version_id)
    if active_only:
        qs = qs.filter(item__status="active", item__deleted_at__isnull=True)
    return {str(i): str(v) for i, v in qs.values_list("item_id", "item_version_id")}


def _kinds_between(old: dict[str, str], new: dict[str, str]) -> dict[str, list[str]]:
    """Change kinds of the item versions after her version up to the target's, for each item that changed."""
    changed = [i for i, v in new.items() if i in old and old[i] != v]
    if not changed:
        return {}
    numbers: dict[str, int] = {}
    rows = list(
        RecallItemVersion.objects.filter(item_id__in=changed, state__in=("live", "superseded")).values_list(
            "item_id", "id", "version_no", "change_kind"
        )
    )
    for _item, vid, no, _kind in rows:
        numbers[str(vid)] = no
    out: dict[str, list[str]] = {}
    for item_id, _vid, no, kind in rows:
        key = str(item_id)
        low, high = numbers.get(old[key]), numbers.get(new[key])
        if low is not None and high is not None and low < no <= high:
            out.setdefault(key, []).append(kind)
    return out


def target_of(sub: RecallSubscription) -> RecallDeckVersion | None:
    """The live version of an active platform deck that is newer than what she has synced, else None."""
    deck = sub.deck
    if deck.kind != "platform" or deck.status != "active" or deck.deleted_at is not None or not deck.live_version_id:
        return None
    live = deck.live_version
    return live if live.version_no > sub.synced_version.version_no else None


def plan_for(sub: RecallSubscription, target: RecallDeckVersion | None = None) -> UpdatePlan | None:
    """The work to move this subscription to `target` (default: the live version), or None when she is already there."""
    target = target or target_of(sub)
    if target is None or target.version_no <= sub.synced_version.version_no:
        return None
    old = _snapshot(sub.synced_version_id, active_only=False)
    new = _snapshot(target.id, active_only=True)
    raw = domain.plan_diff(old, new, _kinds_between(old, new))
    ids = list(raw)
    importance = {
        str(i): imp
        for i, imp in RecallDeckVersionItem.objects.filter(
            deck_version_id__in=[target.id, sub.synced_version_id], item_id__in=ids
        ).values_list("item_id", "item__importance")
    }
    floor = deck_domain.IMPORTANCE_ORDER.index(sub.min_importance)
    held = {
        str(i)
        for i in RecallCard.objects.filter(user_id=sub.user_id, item_id__in=ids)
        .exclude(status="deleted")
        .values_list("item_id", flat=True)
    }
    changes = {
        i: c
        for i, c in raw.items()
        if (i in held) or (c == "added" and deck_domain.IMPORTANCE_ORDER.index(importance.get(i, "bullet")) >= floor)
    }
    skipped = RecallDeckVersion.objects.filter(
        deck_id=sub.deck_id,
        state__in=("live", "superseded"),
        version_no__gt=sub.synced_version.version_no,
        version_no__lt=target.version_no,
    ).count()
    return UpdatePlan(
        sub, target, sub.synced_version.version_no, skipped, changes, domain.summarise(changes), importance
    )


def _own(user_id, subscription_id) -> RecallSubscription:
    sub = (
        RecallSubscription.objects.select_related("deck__live_version", "synced_version", "pending_version")
        .filter(pk=subscription_id, user_id=user_id)
        .first()
    )
    if sub is None:
        raise NotFound("Subscription not found.")
    return sub


def _labels(ids: list[str], versions: dict[str, str]) -> dict[str, str]:
    rows = RecallItemVersion.objects.filter(pk__in=[versions[i] for i in ids if i in versions]).values_list(
        "item_id", "plain_text"
    )
    return {str(i): deck_domain.preview(text.split("\n", 1)[0]) for i, text in rows}


def subscription_of(user_id, subscription_id) -> RecallSubscription:
    """Her subscription, or 404."""
    return _own(user_id, subscription_id)


def preview(user_id, subscription_id) -> UpdatePreview:
    """Counts by kind, a few labelled items per kind and how many of her cards return for re-check (404 for another student's)."""
    sub = _own(user_id, subscription_id)
    plan = plan_for(sub) if sub.status == "active" else None
    if plan is None:
        empty = domain.summarise({})
        return UpdatePreview(
            sub, False, sub.synced_version.version_no, sub.synced_version.version_no, 0, "", empty, {}, {}, 0
        )
    new_versions = _snapshot(plan.target.id, active_only=True)
    old_versions = _snapshot(sub.synced_version_id, active_only=False)
    chosen: dict[str, list[str]] = {}
    more: dict[str, int] = {}
    for kind in domain.PLAN_KINDS:
        ids = sorted(i for i, c in plan.changes.items() if c == kind)
        if ids:
            chosen[kind] = ids[: domain.PREVIEW_PER_KIND]
            more[kind] = max(len(ids) - domain.PREVIEW_PER_KIND, 0)
    labels = _labels(
        [i for ids in chosen.values() for i in ids],
        {**old_versions, **new_versions},  # new overrides old
    )
    items = {
        kind: [PreviewItem(UUID(i), kind, labels.get(i, ""), plan.importance.get(i, "bullet")) for i in ids]
        for kind, ids in chosen.items()
    }
    recheck_ids = [i for i, c in plan.changes.items() if c in domain.RECHECK_CHANGES]
    returning = (
        RecallCard.objects.filter(
            user_id=user_id, item_id__in=recheck_ids, status__in=("active", "suspended"), state__gt=0
        ).count()
        if recheck_ids
        else 0
    )
    return UpdatePreview(
        sub, True, plan.from_no, plan.target.version_no, plan.versions_skipped, plan.target.changelog_md,
        plan.summary, items, more, returning,
    )  # fmt: skip
