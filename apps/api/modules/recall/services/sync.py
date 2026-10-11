"""
Living decks (R2-W2, FR-F15-47 and FR-F15-48): moving a subscription from the deck version she has synced to a newer one.

`sync_subscription` is one transaction under the same per-(student, deck) advisory lock as subscribing. It loads the item diff
between her `synced_version` and the target (`selectors.updates.plan_for`: the WORST change kind across skipped versions
applies per item) and then, per item:

    added         her cards (every cloze ordinal) at or above her `min_importance`; a card she already owns or archived for that
                  item and ordinal is reused with its progress. Unlock mode needs nothing here: the queue keeps the new cards of a
                  `with_coverage` subscription closed until the chapter is started.
    removed       her cards are archived (progress kept) unless the item is still in another active subscription
    typo, clarify the version is swapped silently: `rev` moves, memory and badges do not
    substantive,  the version is swapped, `needs_recheck` is set (reason `content_changed` or `amendment`) and ONE `content_reset`
    amendment     schedule event is written (stability capped at 3 days, due now). During a vacation a `postpone` event follows so
                  the card waits for the day after it. The card row is computed with the same fold `replay_card` uses; the review
                  log is never touched. A card that was never reviewed only swaps its version.

A cloze count change creates or archives the matching cards. The run ends by setting `synced_version`, `pinned_version` and
`last_sync_at` and clearing `pending_version`; a second run with the same target finds nothing to do and writes nothing.

Follow versus pin: a follower is synced by the `recall.sync_subscribers` job after a publish; a pinned subscription only records
`pending_version` until she applies it (`apply_update`). Switching a pinned subscription to follow queues a sync job, never an
inline one. Nothing here logs ids, text or card counts per student beyond a number.
"""

from __future__ import annotations

import logging
import uuid
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from uuid import UUID

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import NotFound

from core import jobs as core_jobs

from .. import registry
from ..domain import decks as deck_domain
from ..domain import limits as lim
from ..domain import sync as domain
from ..domain.folding import CardState, ScheduleEvent, apply_event
from ..domain.scheduling import study_day_start
from ..models import (
    RecallCard,
    RecallDeckVersion,
    RecallDeckVersionItem,
    RecallItem,
    RecallItemVersion,
    RecallScheduleEvent,
    RecallSubscription,
)
from ..selectors import updates
from ..vocab import IMPORTANCE_INT
from . import engine
from .cards import _default_params
from .reviews import card_values
from .subscriptions import _items_in_other_active_subscriptions, _lock

logger = logging.getLogger(__name__)

JOB_SYNC_SUBSCRIBERS = "recall.sync_subscribers"
JOB_SYNC_SUBSCRIPTION = "recall.sync_subscription"
_CARD_FIELDS = (
    "item_version", "status", "subscription", "rev", "updated_at", "needs_recheck", "recheck_reason", "recheck_ref",
    "state", "step", "stability", "difficulty", "due_scheduled_at", "postponed_until", "due_at", "last_review_at", "reps",
    "lapses", "last_lapse_at",
)  # fmt: skip


@dataclass
class SyncResult:
    changed: bool
    from_version_no: int
    to_version_no: int
    versions_skipped: int = 0
    added: int = 0  # items, by kind of change
    removed: int = 0
    silent: int = 0
    rechecked: int = 0
    cards_created: int = 0  # cards
    cards_restored: int = 0
    cards_archived: int = 0
    cards_updated: int = 0
    cards_reset: int = 0

    def as_dict(self) -> dict:
        return asdict(self)


def _noop(sub: RecallSubscription, target: RecallDeckVersion | None) -> SyncResult:
    no = sub.synced_version.version_no
    return SyncResult(False, no, target.version_no if target is not None else no)


def _target(sub: RecallSubscription, target_version_id) -> RecallDeckVersion | None:
    if target_version_id is None:
        return updates.target_of(sub) or (sub.deck.live_version if sub.deck.live_version_id else None)
    version = RecallDeckVersion.objects.filter(
        pk=target_version_id, deck_id=sub.deck_id, state__in=("live", "superseded")
    ).first()
    if version is None:
        raise NotFound("Deck version not found.")
    return version


def _wake_during_vacation(eng: engine.Engine, now: datetime) -> datetime | None:
    until = eng.settings.vacation_until
    if until is None or eng.local_date(now) > until:
        return None
    return study_day_start(until + timedelta(days=1), eng.settings.tz, eng.settings.day_start_hour)


def _reset(card: RecallCard, eng: engine.Engine, now: datetime, reason: str, ref: str) -> list[RecallScheduleEvent]:
    """The `content_reset` (and a vacation `postpone`) of one reviewed card, and the card row folded from them."""
    cap = lim.CONTENT_RESET_STABILITY_CAP_DAYS
    reset = RecallScheduleEvent(
        id=uuid.uuid4(), user_id=card.user_id, card=card, kind="content_reset", at=now, from_due=card.due_at,
        stability_before=card.stability, stability_after=cap, reason_code=reason, ref=ref,
    )  # fmt: skip
    state = CardState(engine.memory_of(card), card.due_scheduled_at, card.postponed_until)
    state = apply_event(
        state, ScheduleEvent(str(reset.id), now, "content_reset", cap_days=cap), eng.weights, eng.cfg, card_id=card.id
    )
    events = [reset]
    wake = _wake_during_vacation(eng, now)
    if wake is not None:
        at = now + timedelta(microseconds=1)
        hold = RecallScheduleEvent(
            id=uuid.uuid4(), user_id=card.user_id, card=card, kind="postpone", at=at, from_due=now, to_due=wake,
            reason_code="vacation", ref=ref,
        )  # fmt: skip
        state = apply_event(
            state, ScheduleEvent(str(hold.id), at, "postpone", to_due=wake), eng.weights, eng.cfg, card_id=card.id
        )
        events.append(hold)
    for column, value in card_values(card, state, eng, now).items():
        setattr(card, column, value)
    reset.to_due = card.due_scheduled_at
    return events


def _reason_for(current: str | None, kind: str) -> str:
    """`amendment` outranks `content_changed` when a card is flagged for both."""
    new = domain.RECHECK_REASON[kind]
    return "amendment" if "amendment" in (current, new) else new


def _card_kind(card: RecallCard, version: RecallItemVersion, history: dict) -> str | None:
    """How her card's version differs from the target's: the worst kind between them, None when it is the same version."""
    if card.item_version_id == version.id:
        return None
    low = card.item_version.version_no
    kinds = [kind for no, kind in history.get(card.item_id, ()) if low < no <= version.version_no]
    return domain.worst_change(kinds) or "substantive"


def sync_subscription(user_id, subscription_id, *, target_version_id=None, now: datetime | None = None) -> SyncResult:
    """
    Bring one active subscription to the target deck version (default: the live one). Idempotent per target: when she is already
    there nothing is written. 404 for another student's subscription or a version that is not this deck's.
    """
    now = now or timezone.now()
    with transaction.atomic():
        probe = (
            RecallSubscription.objects.filter(pk=subscription_id, user_id=user_id)
            .values_list("deck_id", flat=True)
            .first()
        )
        if probe is None:
            raise NotFound("Subscription not found.")
        _lock(user_id, probe)
        sub = (
            RecallSubscription.objects.select_for_update(of=("self",))
            .select_related("deck__live_version", "synced_version")
            .get(pk=subscription_id, user_id=user_id)
        )
        target = _target(sub, target_version_id)
        if sub.status != "active" or target is None or target.version_no <= sub.synced_version.version_no:
            if sub.pending_version_id and (target is None or target.version_no >= sub.pending_version.version_no):
                sub.pending_version = None
                sub.save(update_fields=["pending_version"])
            return _noop(sub, target)
        plan = updates.plan_for(sub, target)
        result = SyncResult(
            True, sub.synced_version.version_no, target.version_no, plan.versions_skipped if plan else 0
        )
        if plan is not None and plan.changes:
            _apply(sub, target, plan, result, now)
        sub.synced_version = sub.pinned_version = target
        sub.pending_version, sub.last_sync_at = None, now
        sub.save(update_fields=["synced_version", "pinned_version", "pending_version", "last_sync_at"])
    logger.info("recall subscription synced", extra={"cards_changed": result.cards_updated + result.cards_created})
    return result


def _apply(sub: RecallSubscription, target: RecallDeckVersion, plan, result: SyncResult, now: datetime) -> None:
    user_id = sub.user_id
    eng = engine.load(user_id)
    ids = list(plan.changes)
    items = {str(i.id): i for i in RecallItem.objects.filter(pk__in=ids)}
    rows = {
        str(r.item_id): r.item_version
        for r in RecallDeckVersionItem.objects.filter(deck_version=target, item_id__in=ids).select_related(
            "item_version"
        )
    }
    history: dict = defaultdict(list)
    for item_id, no, kind in RecallItemVersion.objects.filter(
        item_id__in=ids, state__in=("live", "superseded")
    ).values_list("item_id", "version_no", "change_kind"):
        history[item_id].append((no, kind))
    held: dict[str, dict[int, RecallCard]] = defaultdict(dict)
    for card in (
        RecallCard.objects.select_for_update(of=("self",))
        .select_related("item_version")
        .filter(user_id=user_id, item_id__in=ids)
        .exclude(status="deleted")
        .order_by("id")
    ):
        held[str(card.item_id)][card.ordinal] = card
    elsewhere = _items_in_other_active_subscriptions(user_id, sub) if "removed" in plan.changes.values() else {}
    floor = deck_domain.IMPORTANCE_ORDER.index(sub.min_importance)
    params = _default_params()
    ref = f"dv:{target.id}"
    fresh: list[RecallCard] = []
    touched: dict[UUID, RecallCard] = {}
    events: list[RecallScheduleEvent] = []
    seen = {"silent": set(), "recheck": set()}

    def touch(card: RecallCard) -> RecallCard:
        card.rev += 1
        card.updated_at = now
        touched[card.pk] = card
        return card

    for item_id, change in plan.changes.items():
        item, mine = items[item_id], held.get(item_id, {})
        if change == "removed":
            result.removed += 1
            for card in mine.values():
                if card.status == "archived":
                    continue
                if item.id in elsewhere:
                    card.subscription_id = elsewhere[item.id]
                else:
                    card.status = "archived"
                    result.cards_archived += 1
                touch(card)
            continue
        version = rows[item_id]
        spec = registry.get_kind(item.kind)
        wanted = set(spec.ordinals({k: v for k, v in version.fields.items() if k != "v"}))
        above_floor = deck_domain.IMPORTANCE_ORDER.index(item.importance) >= floor
        if change == "added":
            result.added += 1
        for ordinal in sorted(wanted):
            card = mine.get(ordinal)
            if card is None:
                if above_floor:
                    fresh.append(
                        RecallCard(
                            user_id=user_id, item=item, ordinal=ordinal, subscription=sub, item_version=version,
                            chapter_id=item.chapter_id, subject_key=item.subject_key,
                            importance=IMPORTANCE_INT[item.importance], scheduler_version=lim.SCHEDULER_VERSION, params=params,
                        )
                    )  # fmt: skip
                continue
            kind = _card_kind(card, version, history)
            if card.status == "archived" and change == "added" and above_floor:
                card.status, card.subscription_id = "active", sub.pk
                result.cards_restored += 1
                touch(card)
            if kind is None:
                continue
            card.item_version = version
            touch(card)
            if kind in domain.SILENT_CHANGES:
                seen["silent"].add(item_id)
            elif card.state > 0:
                events += _reset(card, eng, now, domain.RESET_REASON[kind], ref)
                card.recheck_reason = _reason_for(card.recheck_reason if card.needs_recheck else None, kind)
                card.needs_recheck, card.recheck_ref = True, None
                result.cards_reset += 1
                seen["recheck"].add(item_id)
        for ordinal, card in mine.items():
            if ordinal not in wanted and card.status != "archived":
                card.status = "archived"
                result.cards_archived += 1
                touch(card)
    result.silent, result.rechecked = len(seen["silent"]), len(seen["recheck"])
    RecallCard.objects.bulk_create(fresh)
    result.cards_created = len(fresh)
    result.cards_updated = len(touched)
    if touched:
        RecallCard.objects.bulk_update(list(touched.values()), list(_CARD_FIELDS), batch_size=200)
    if events:
        RecallScheduleEvent.objects.bulk_create(events, batch_size=500)


# ---------------------------------------------------------------------------------------- follow, pin, apply
def apply_update(user_id, subscription_id) -> SyncResult:
    """She taps Apply: sync to the live version now. Idempotent; a second tab (or a follower job) that got there first makes it a no-op."""
    return sync_subscription(user_id, subscription_id)


def queue_sync(subscription_id, version_id) -> None:
    """One subscription again through the queue (a pin switched to follow, a resubscribe), merged with a job already waiting."""
    core_jobs.enqueue(
        JOB_SYNC_SUBSCRIPTION,
        {"subscription_id": str(subscription_id), "deck_version_id": str(version_id)},
        dedupe_key=f"{JOB_SYNC_SUBSCRIPTION}:{subscription_id}:{version_id}",
    )


def set_follow(user_id, subscription_id, follow: bool) -> RecallSubscription:
    """
    Switch between follow and pin. Pin to follow with a newer version waiting queues the sync job (never inline); follow to pin only
    stops future syncs. Idempotent.
    """
    with transaction.atomic():
        probe = (
            RecallSubscription.objects.filter(pk=subscription_id, user_id=user_id)
            .values_list("deck_id", flat=True)
            .first()
        )
        if probe is None:
            raise NotFound("Subscription not found.")
        _lock(user_id, probe)
        sub = (
            RecallSubscription.objects.select_for_update(of=("self",))
            .select_related("deck__live_version", "synced_version")
            .get(pk=subscription_id, user_id=user_id)
        )
        if sub.follow_updates != follow:
            sub.follow_updates = follow
            sub.save(update_fields=["follow_updates"])
        if follow and sub.status == "active":
            target = updates.target_of(sub)
            if target is not None:
                queue_sync(sub.pk, target.id)
        return sub


def after_resubscribe(sub: RecallSubscription) -> None:
    """A subscription that comes back finds the deck changed: a follower is queued, a pinned one records the pending version."""
    sub = RecallSubscription.objects.select_related("deck__live_version", "synced_version").get(pk=sub.pk)
    target = updates.target_of(sub)
    if target is None:
        return
    if sub.follow_updates:
        queue_sync(sub.pk, target.id)
    else:
        RecallSubscription.objects.filter(pk=sub.pk).update(pending_version=target)


# ------------------------------------------------------------------------------------------ fan-out
@dataclass
class ChunkResult:
    followed: int = 0  # followers brought to the version
    pinned: int = 0  # pinned subscriptions that now record a pending version
    failed: int = 0
    next_after: UUID | None = None  # the cursor of the next chunk, None when this was the last


def sync_chunk(version_id, after: UUID | None = None, *, limit: int | None = None) -> ChunkResult:
    """
    One chunk of the fan-out of a published deck version: up to `limit` active subscriptions of the deck in id order after `after`.
    A follower is synced (each in its own transaction, so one failure never stops the chunk: it is counted and queued for its own
    retry job); a pinned subscription records the pending version. Safe to run twice.
    """
    limit = limit or domain.SYNC_CHUNK
    version = RecallDeckVersion.objects.select_related("deck").filter(pk=version_id).first()
    if version is None or version.deck.live_version_id != version.id:
        return ChunkResult()  # superseded meanwhile: the next version's fan-out covers everyone
    qs = RecallSubscription.objects.filter(deck_id=version.deck_id, status="active").order_by("id")
    if after is not None:
        qs = qs.filter(id__gt=after)
    rows = list(qs.values_list("id", "user_id", "follow_updates")[:limit])
    out = ChunkResult(next_after=rows[-1][0] if len(rows) == limit else None)
    pinned_ids = []
    for sub_id, user_id, follow in rows:
        if not follow:
            pinned_ids.append(sub_id)
            continue
        try:
            with transaction.atomic():
                if sync_subscription(user_id, sub_id, target_version_id=version.id).changed:
                    out.followed += 1
        except Exception:  # noqa: BLE001 - one subscription must not stop the chunk; it gets its own retry job
            logger.warning("recall subscription sync failed", exc_info=False)
            out.failed += 1
            queue_sync(sub_id, version.id)
    if pinned_ids:
        out.pinned = RecallSubscription.objects.filter(
            pk__in=pinned_ids, synced_version__version_no__lt=version.version_no
        ).update(pending_version=version)
    return out


def _jobs_of(version_id):
    from core.models import Job

    return Job.objects.filter(
        type__in=(JOB_SYNC_SUBSCRIBERS, JOB_SYNC_SUBSCRIPTION), payload__deck_version_id=str(version_id)
    )


def retry_failed(version_id) -> int:
    """Staff: queue every failed sync job of this deck version again (attempts reset). Returns how many were requeued."""
    from core.models import Job

    return (
        _jobs_of(version_id)
        .filter(status=Job.Status.FAILED)
        .update(
            status=Job.Status.QUEUED,
            attempts=0,
            run_after=timezone.now(),
            finished_at=None,
            last_error="",
            locked_at=None,
        )
    )


def fanout_stats(version_id) -> dict[str, int]:
    """Staff summary after a publish: sync jobs queued, running, done and failed for this deck version (counts only)."""
    from django.db.models import Count

    stats = {"queued": 0, "running": 0, "done": 0, "failed": 0}
    for status, n in _jobs_of(version_id).values_list("status").annotate(n=Count("id")):
        stats[status] = n
    return stats
