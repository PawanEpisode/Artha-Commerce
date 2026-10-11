"""
The batch path of `submit_reviews` (R2-W0): the common case of an offline sync, applied with a fixed number of queries.

An event takes this path only when the whole outcome is knowable without looking at anything else: the card exists, is live,
and has no newer fact in the log; the mode counts; the event is not late and not for older content. Everything else (undo
targets, cram, late, stale, deleted, a card that needs a replay, anything unknown or invalid) goes to `submit_review`, the
one-event path, exactly as before. The two paths write the same log row, the same card row, the same counters; a test holds
them equal for any batch, so this module changes speed, never behaviour.

Per batch: one query for existing ids, one for the cards, two aggregates for the replay check, one for sessions, one for sibling
cards, then one bulk insert of the log rows, one bulk update of the cards, and a handful of counter upserts. Card text, prompts
and answers are never read here; ids and numbers only.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from datetime import datetime
from typing import Any

from django.db import transaction
from django.db.models import F, Max
from django.utils import timezone

from ..domain import limits as lim
from ..domain.fsrs6 import review as fsrs_review
from ..models import RecallCard, RecallReviewLog, RecallScheduleEvent, RecallSession
from . import rollups
from .engine import Engine, memory_of
from .reviews import (
    APPLIED,
    DUPLICATE,
    MODES,
    RATING_FIELD,
    STATE_CHANGING,
    ReviewIn,
    ReviewResult,
    _apply_fast,
    _bury_siblings,
    _check_leech,
    _classify,
    _derived,
    submit_review,
)

CARD_COLUMNS = (
    "state",
    "step",
    "stability",
    "difficulty",
    "due_scheduled_at",
    "postponed_until",
    "due_at",
    "last_review_at",
    "reps",
    "lapses",
    "last_lapse_at",
    "scheduler_version",
    "rev",
    "updated_at",
)


class _Pending:
    """Fast-path work not yet written: log rows, the cards they changed and the counters they add."""

    def __init__(self) -> None:
        self.rows: list[RecallReviewLog] = []
        self.cards: dict[Any, RecallCard] = {}
        self.daily: dict[Any, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        self.chapter: dict[tuple, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        self.sessions: dict[Any, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        self.bury: list[tuple[RecallCard, datetime]] = []
        self.leech: list[RecallCard] = []


def _flush(user_id, p: _Pending, eng: Engine, now: datetime, cards: dict) -> None:
    if not p.rows:
        return
    RecallReviewLog.objects.bulk_create(p.rows)
    stamp = timezone.now()
    for c in p.cards.values():
        c.updated_at = stamp
    RecallCard.objects.bulk_update(list(p.cards.values()), CARD_COLUMNS)
    for day, deltas in p.daily.items():
        rollups.bump_daily(user_id, day, deltas)
    for (day, chapter_id), deltas in p.chapter.items():
        rollups.bump_chapter(user_id, day, chapter_id, deltas)
    for session_id, deltas in p.sessions.items():
        updates: dict[str, Any] = {k: F(k) + v for k, v in deltas.items() if k != "touch"}
        updates["last_event_at"] = now
        RecallSession.objects.filter(id=session_id).update(**updates)
    for card in p.leech:
        _check_leech(card, eng)
    if p.bury:
        touched = {card.item_id for card, _ in p.bury}
        for card, reviewed_at in p.bury:
            _bury_siblings(card, eng, reviewed_at, now)
        # burying bumps a sibling's `rev` in the database; take it back so a later event never writes an old one
        stale = [c for c in cards.values() if c.item_id in touched]
        fresh = {
            row[0]: row
            for row in RecallCard.objects.filter(id__in=[c.id for c in stale]).values_list("id", "rev", "buried_until")
        }
        for c in stale:
            if c.id in fresh:
                c.rev, c.buried_until = fresh[c.id][1], fresh[c.id][2]
    p.__init__()


def apply_batch(
    user_id, evs: Sequence[ReviewIn], order: Sequence[int], eng: Engine, now: datetime
) -> list[ReviewResult | None]:
    """Apply `evs` in `order`; the caller has locked the cards and holds the transaction. Raises IntegrityError on a race."""
    results: list[ReviewResult | None] = [None] * len(evs)
    ids = [e.id for e in evs]
    existing = set(RecallReviewLog.objects.filter(user_id=user_id, id__in=ids).values_list("id", flat=True))
    card_ids = {e.card_id for e in evs}
    cards = {c.id: c for c in RecallCard.objects.filter(user_id=user_id, id__in=card_ids)}
    last_review = dict(
        RecallReviewLog.objects.filter(user_id=user_id, card_id__in=card_ids, kind="review", counts_for_scheduling=True)
        .values_list("card_id")
        .annotate(at=Max("reviewed_at"))
    )
    last_sched = dict(
        RecallScheduleEvent.objects.filter(user_id=user_id, card_id__in=card_ids, kind__in=STATE_CHANGING)
        .values_list("card_id")
        .annotate(at=Max("at"))
    )
    session_ids = {e.session_id for e in evs if e.session_id is not None}
    live_sessions = (
        set(RecallSession.objects.filter(user_id=user_id, id__in=session_ids).values_list("id", flat=True))
        if session_ids
        else set()
    )
    item_ids = {c.item_id for c in cards.values()}
    with_siblings: set = set()
    if eng.settings.bury_siblings and item_ids:
        per_item: dict = defaultdict(int)
        for item_id in RecallCard.objects.filter(user_id=user_id, item_id__in=item_ids, status="active").values_list(
            "item_id", flat=True
        ):
            per_item[item_id] += 1
        with_siblings = {i for i, n in per_item.items() if n > 1}

    pending = _Pending()
    applied_ids: set = set()
    dirty: set = set()  # cards a one-event call has touched; their in-memory copy is no longer the truth
    for i in order:
        ev = evs[i]
        card = cards.get(ev.card_id)
        if ev.id in applied_ids or (ev.id in existing and card is not None):
            results[i] = ReviewResult(ev.id, DUPLICATE, "", False, card)
            continue
        eligible = (
            card is not None
            and ev.card_id not in dirty
            and ev.rating in (1, 2, 3, 4)
            and ev.mode in MODES
            and ev.mode != "cram"
            and (ev.item_version_id is None or ev.item_version_id == card.item_version_id)
            and card.status != "deleted"
            and card.deleted_at is None
        )
        if eligible:
            reviewed_at, flags, late, deleted, stale, counts = _classify(ev, card, now)
            newest = last_review.get(card.id)
            sched = last_sched.get(card.id)
            eligible = (
                counts
                and not late
                and (newest is None or newest < reviewed_at)
                and (sched is None or sched <= reviewed_at)
            )
        if not eligible:
            _flush(user_id, pending, eng, now, cards)
            if card is not None:
                dirty.add(card.id)
            with transaction.atomic():
                results[i] = submit_review(user_id, ev, now=now, eng=eng)
            continue

        duration = None if ev.duration_ms is None else max(0, min(int(ev.duration_ms), lim.DURATION_CAP_MS))
        session_id = ev.session_id if ev.session_id in live_sessions else None
        memory = memory_of(card)
        out = fsrs_review(
            memory, ev.rating, reviewed_at, eng.weights, eng.cfg_at(card.importance, reviewed_at), card_id=card.id
        )
        local_date = eng.local_date(reviewed_at)
        pending.rows.append(
            RecallReviewLog(
                user_id=user_id,
                id=ev.id,
                kind="review",
                card_id=card.id,
                item_id=card.item_id,
                item_version_id=ev.item_version_id if ev.item_version_id is not None else card.item_version_id,
                session_id=session_id,
                rating=ev.rating,
                reviewed_at=reviewed_at,
                received_at=now,
                duration_ms=duration,
                mode=ev.mode,
                counts_for_scheduling=True,
                device_id=ev.device_id,
                tz_offset_min=ev.tz_offset_min,
                local_date=local_date,
                flags=flags,
                phase_before=out.phase_before,
                stability_before=memory.stability,
                difficulty_before=memory.difficulty,
                elapsed_days=out.elapsed_days,
                retrievability_before=out.retrievability_before,
                **_derived(out, eng.params_id, lim.SCHEDULER_VERSION),
            )
        )
        _apply_fast(card, out, eng, now)
        pending.cards[card.id] = card
        last_review[card.id] = reviewed_at
        applied_ids.add(ev.id)
        for name, amount in rollups.daily_deltas(
            phase_before=out.phase_before, rating=ev.rating, importance=card.importance, duration_ms=duration
        ).items():
            pending.daily[local_date][name] += amount
        for name, amount in rollups.chapter_deltas(rating=ev.rating, importance=card.importance).items():
            pending.chapter[(local_date, card.chapter_id)][name] += amount
        if session_id is not None:
            s = pending.sessions[session_id]
            s["reviewed"] += 1
            s["active_seconds"] += (duration or 0) // 1000
            if out.phase_before == 0:
                s["new_count"] += 1
            s[RATING_FIELD[ev.rating]] += 1
        if card.lapses >= eng.settings.leech_threshold and not card.leech:
            pending.leech.append(card)
        if card.item_id in with_siblings:
            pending.bury.append((card, reviewed_at))
        results[i] = ReviewResult(ev.id, APPLIED, "", False, card)
    _flush(user_id, pending, eng, now, cards)
    return results
