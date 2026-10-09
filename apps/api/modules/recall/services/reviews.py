"""
Reviews (ERD 3.5): the append-only log is the truth and the card row is a cache of it.

`submit_review` is one transaction: lock the card, refuse a duplicate, classify the event (late, clamped, stale, cram, deleted
card), insert the log row, then take the FAST path (one `fsrs6.review` from the card's state, derived columns written in the same
insert) or the REPLAY path (insert, then fold the whole card again) when the event is not the newest fact about the card.
Rollups and session counters move only for a newly inserted row. Nothing here logs or returns card text; ids and numbers only.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from django.db import IntegrityError, transaction
from django.db.models import F, Q
from django.utils import timezone
from rest_framework.exceptions import NotFound

from core import events

from ..domain import limits as lim
from ..domain.folding import ReviewEvent, ScheduleEvent, effective_due, fold_trace
from ..domain.fsrs6 import review as fsrs_review
from ..domain.scheduling import end_of_study_day
from ..errors import BatchTooLarge, NotUndoable
from ..models import (
    RecallCard,
    RecallItemVersion,
    RecallReviewLog,
    RecallScheduleEvent,
    RecallSession,
)
from . import log_guard, rollups
from .engine import Engine, load, memory_of

logger = logging.getLogger(__name__)

MODES = RecallReviewLog.MODES
STATE_CHANGING = ("forget", "content_reset", "postpone", "unpostpone")
STALE_KINDS = ("substantive", "amendment")
RATING_FIELD = {1: "again", 2: "hard", 3: "good", 4: "easy"}

APPLIED, DUPLICATE, DELETED, STALE, LATE, INVALID = (
    "applied",
    "duplicate",
    "applied_to_deleted",
    "stale_content",
    "late_unapplied",
    "invalid",
)


@dataclass(frozen=True)
class ReviewIn:
    id: uuid.UUID
    card_id: uuid.UUID
    rating: int
    reviewed_at: datetime
    duration_ms: int | None = None
    session_id: uuid.UUID | None = None
    mode: str = "normal"
    item_version_id: uuid.UUID | None = None
    device_id: str | None = None
    tz_offset_min: int = 0


@dataclass
class ReviewResult:
    event_id: uuid.UUID
    status: str
    reason: str = ""
    merged: bool = False
    card: RecallCard | None = None


@dataclass
class UndoResult:
    undo_id: uuid.UUID
    voids_id: uuid.UUID
    card: RecallCard | None
    existing: bool = False


# ------------------------------------------------------------------------------------------------------ helpers
def _lock_card(user_id, card_id) -> RecallCard | None:
    return RecallCard.objects.select_for_update(of=("self",)).filter(user_id=user_id, id=card_id).first()


def _derived(out, params_id, version: str) -> dict[str, Any]:
    st = out.state
    return {
        "phase_after": st.phase,
        "stability_after": st.stability,
        "difficulty_after": st.difficulty,
        "scheduled_days": out.scheduled_days,
        "due_after": out.due_at,
        "params_id": params_id,
        "scheduler_version": version,
    }


def _is_stale(card: RecallCard, event_version_id) -> bool:
    if event_version_id is None or event_version_id == card.item_version_id:
        return False
    theirs = (
        RecallItemVersion.objects.filter(id=event_version_id, item_id=card.item_id)
        .values_list("version_no", flat=True)
        .first()
    )
    if theirs is None:
        return False
    return RecallItemVersion.objects.filter(
        item_id=card.item_id, version_no__gt=theirs, change_kind__in=STALE_KINDS
    ).exists()


def _needs_replay(user_id, card_id, at: datetime) -> bool:
    newer_review = RecallReviewLog.objects.filter(
        user_id=user_id, card_id=card_id, kind="review", counts_for_scheduling=True, reviewed_at__gte=at
    ).exists()
    if newer_review:
        return True
    return RecallScheduleEvent.objects.filter(
        user_id=user_id, card_id=card_id, kind__in=STATE_CHANGING, at__gt=at
    ).exists()


def _apply_fast(card: RecallCard, out, eng: Engine) -> None:
    st = out.state
    card.state, card.step = st.phase, st.step
    card.stability, card.difficulty = st.stability, st.difficulty
    card.due_scheduled_at = out.due_at
    card.postponed_until = None
    card.due_at = out.due_at
    card.last_review_at, card.reps = st.last_review_at, st.reps
    card.lapses, card.last_lapse_at = st.lapses, st.last_lapse_at
    card.scheduler_version = lim.SCHEDULER_VERSION
    card.rev += 1


def _session_bump(session_id, *, sign: int, phase_before, rating, duration_ms, now: datetime | None) -> None:
    updates: dict[str, Any] = {
        "reviewed": F("reviewed") + sign,
        "active_seconds": F("active_seconds") + sign * ((duration_ms or 0) // 1000),
    }
    if phase_before == 0:
        updates["new_count"] = F("new_count") + sign
    if rating in RATING_FIELD:
        field = RATING_FIELD[rating]
        updates[field] = F(field) + sign
    if now is not None:
        updates["last_event_at"] = now
    RecallSession.objects.filter(id=session_id).update(**updates)


def _bury_siblings(card: RecallCard, eng: Engine, reviewed_at: datetime, now: datetime) -> None:
    s = eng.settings
    if not s.bury_siblings:
        return
    until = end_of_study_day(now, s.tz, s.day_start_hour)
    if reviewed_at < until - timedelta(days=1):  # an old offline event never buries today's siblings
        return
    RecallCard.objects.filter(user_id=card.user_id, item_id=card.item_id, status="active").exclude(id=card.id).filter(
        Q(buried_until__isnull=True) | Q(buried_until__lt=until)
    ).update(buried_until=until, rev=F("rev") + 1)


def _check_leech(card: RecallCard, eng: Engine) -> None:
    if card.leech or card.lapses < eng.settings.leech_threshold:
        return
    card.leech = True
    card.save(update_fields=["leech", "updated_at"])
    payload = {"user_id": str(card.user_id), "card_id": str(card.id), "lapses": card.lapses}
    transaction.on_commit(lambda: events.emit("recall_leech_detected", **payload))


# ------------------------------------------------------------------------------------------------------ submit
def submit_review(user_id, ev: ReviewIn, *, now: datetime | None = None, eng: Engine | None = None) -> ReviewResult:
    now = now or timezone.now()
    if ev.rating not in (1, 2, 3, 4):
        return ReviewResult(ev.id, INVALID, "bad_rating")
    if ev.mode not in MODES:
        return ReviewResult(ev.id, INVALID, "bad_mode")
    with transaction.atomic():
        eng = eng or load(user_id)
        card = _lock_card(user_id, ev.card_id)
        if card is None:
            return ReviewResult(ev.id, INVALID, "unknown_card")
        existing = RecallReviewLog.objects.filter(user_id=user_id, id=ev.id).first()
        if existing is not None:
            return ReviewResult(ev.id, DUPLICATE, "", False, card)
        return _insert(user_id, ev, card, eng, now)


def _insert(user_id, ev: ReviewIn, card: RecallCard, eng: Engine, now: datetime) -> ReviewResult:
    flags: list[str] = []
    reviewed_at = ev.reviewed_at
    if reviewed_at > now + timedelta(minutes=lim.CLOCK_SKEW_MINUTES):
        reviewed_at = now
        flags.append("clamped_time")
    late = reviewed_at < now - timedelta(days=lim.OFFLINE_EVENT_MAX_AGE_DAYS)
    if late:
        flags.append("late")
    deleted = card.status == "deleted" or card.deleted_at is not None
    if deleted:
        flags.append("deleted_card")
    stale = not deleted and _is_stale(card, ev.item_version_id)
    if stale:
        flags.append("stale_content")
    counts = ev.mode != "cram" and not late and not stale and not deleted
    duration = None if ev.duration_ms is None else max(0, min(int(ev.duration_ms), lim.DURATION_CAP_MS))
    session_id = ev.session_id
    if session_id is not None and not RecallSession.objects.filter(user_id=user_id, id=session_id).exists():
        session_id = None
    version_id = ev.item_version_id if ev.item_version_id is not None else card.item_version_id
    memory = memory_of(card)
    fields: dict[str, Any] = {
        "user_id": user_id,
        "id": ev.id,
        "kind": "review",
        "card_id": card.id,
        "item_id": card.item_id,
        "item_version_id": version_id,
        "session_id": session_id,
        "rating": ev.rating,
        "reviewed_at": reviewed_at,
        "received_at": now,
        "duration_ms": duration,
        "mode": ev.mode,
        "counts_for_scheduling": counts,
        "device_id": ev.device_id,
        "tz_offset_min": ev.tz_offset_min,
        "local_date": eng.local_date(reviewed_at),
        "flags": flags,
        "phase_before": memory.phase,
    }
    replay = counts and _needs_replay(user_id, card.id, reviewed_at)
    out = None
    if replay:
        fields["phase_before"] = None  # written by the replay; until then no rollup has counted this row
    if counts and not replay:
        out = fsrs_review(memory, ev.rating, reviewed_at, eng.weights, eng.cfg, card_id=card.id)
        fields.update(
            stability_before=memory.stability,
            difficulty_before=memory.difficulty,
            elapsed_days=out.elapsed_days,
            retrievability_before=out.retrievability_before,
            phase_before=out.phase_before,
            **_derived(out, eng.params_id, lim.SCHEDULER_VERSION),
        )
    try:
        with transaction.atomic():
            RecallReviewLog.objects.create(**fields)
    except IntegrityError:
        return ReviewResult(ev.id, DUPLICATE, "", False, card)

    if out is not None:
        _apply_fast(card, out, eng)
        card.save()
    elif replay:
        replay_card(user_id, card.id, eng=eng, locked=card)
        card.refresh_from_db()
        row = RecallReviewLog.objects.get(user_id=user_id, id=ev.id)
        fields["phase_before"] = row.phase_before
    elif stale:
        card.needs_recheck = True
        card.recheck_reason = card.recheck_reason or "content_changed"
        card.rev += 1
        card.save(update_fields=["needs_recheck", "recheck_reason", "rev", "updated_at"])

    rollups.apply_row(
        user_id,
        local_date=fields["local_date"],
        chapter_id=card.chapter_id,
        phase_before=fields["phase_before"],
        rating=ev.rating,
        importance=card.importance,
        duration_ms=duration,
    )
    if session_id is not None:
        _session_bump(
            session_id, sign=1, phase_before=fields["phase_before"], rating=ev.rating, duration_ms=duration, now=now
        )
    if counts:
        _check_leech(card, eng)
        _bury_siblings(card, eng, reviewed_at, now)
    status = DELETED if deleted else STALE if stale else LATE if late else APPLIED
    return ReviewResult(ev.id, status, "", replay, card)


def submit_reviews(
    user_id, evs: Sequence[ReviewIn], *, now: datetime | None = None
) -> tuple[list[ReviewResult], list[RecallCard]]:
    """Up to 100 events, each in its own savepoint, applied in time order. A bad event never fails the others."""
    if len(evs) > lim.BATCH_MAX_EVENTS:
        raise BatchTooLarge
    now = now or timezone.now()
    order = sorted(range(len(evs)), key=lambda i: (evs[i].reviewed_at, str(evs[i].id), i))
    with transaction.atomic():
        eng = load(user_id)
        ids = sorted({e.card_id for e in evs}, key=str)
        # Lock every card of the batch up front in one fixed order, so two batches over the same cards cannot deadlock
        list(RecallCard.objects.select_for_update(of=("self",)).filter(user_id=user_id, id__in=ids).order_by("id"))
        results: list[ReviewResult | None] = [None] * len(evs)
        for i in order:
            with transaction.atomic():
                results[i] = submit_review(user_id, evs[i], now=now, eng=eng)
        cards = list(RecallCard.objects.filter(user_id=user_id, id__in=ids))
    return [r for r in results if r is not None], cards


# ------------------------------------------------------------------------------------------------------ replay
def replay_card(user_id, card_id, *, eng: Engine | None = None, locked: RecallCard | None = None) -> bool:
    """Fold the card's facts again and write the result back (derived log columns, rollup phase moves, the card row)."""
    with transaction.atomic():
        eng = eng or load(user_id)
        card = locked or _lock_card(user_id, card_id)
        if card is None:
            raise NotFound("Card not found.")
        rows = list(
            RecallReviewLog.objects.filter(user_id=user_id, card_id=card.id, kind="review").order_by(
                "reviewed_at", "id"
            )
        )
        voided = set(
            RecallReviewLog.objects.filter(user_id=user_id, card_id=card.id, kind="undo").values_list(
                "voids_id", flat=True
            )
        )
        sched = list(RecallScheduleEvent.objects.filter(user_id=user_id, card_id=card.id, kind__in=STATE_CHANGING))
        facts: list[ReviewEvent | ScheduleEvent] = [
            ReviewEvent(str(r.id), r.reviewed_at, r.rating, r.counts_for_scheduling, r.id in voided) for r in rows
        ]
        facts += [
            ScheduleEvent(str(e.id), e.at, e.kind, e.to_due, e.stability_after if e.kind == "content_reset" else None)
            for e in sched
        ]
        state, traces = fold_trace(facts, eng.weights, eng.cfg, card_id=card.id)
        with log_guard.replaying():
            for r in rows:
                t = traces[str(r.id)]
                o = t.outcome
                cols: dict[str, Any] = {
                    "phase_before": t.phase_before,
                    "stability_before": t.state_before.stability,
                    "difficulty_before": t.state_before.difficulty,
                    "elapsed_days": o.elapsed_days if o else None,
                    "retrievability_before": o.retrievability_before if o else None,
                    "phase_after": o.state.phase if o else None,
                    "stability_after": o.state.stability if o else None,
                    "difficulty_after": o.state.difficulty if o else None,
                    "scheduled_days": o.scheduled_days if o else None,
                    "due_after": o.due_at if o else None,
                    "params_id": eng.params_id if o else r.params_id,
                    "scheduler_version": lim.SCHEDULER_VERSION if o else r.scheduler_version,
                }
                if any(getattr(r, k) != v for k, v in cols.items()):
                    RecallReviewLog.objects.filter(user_id=user_id, id=r.id).update(**cols)
                if r.id not in voided and r.phase_before is not None and r.phase_before != t.phase_before:
                    old = rollups.daily_deltas(
                        phase_before=r.phase_before, rating=None, importance=0, duration_ms=0, sign=-1
                    )
                    new = rollups.daily_deltas(
                        phase_before=t.phase_before, rating=None, importance=0, duration_ms=0, sign=1
                    )
                    old.pop("seconds", None), new.pop("seconds", None)
                    rollups.bump_daily(user_id, r.local_date, {**old, **new})
        return _write_card(card, state)


def _write_card(card: RecallCard, state) -> bool:
    m = state.memory
    new_values = {
        "state": m.phase,
        "step": m.step,
        "stability": m.stability,
        "difficulty": m.difficulty,
        "due_scheduled_at": state.due_scheduled_at,
        "postponed_until": state.postponed_until,
        "due_at": effective_due(state),
        "last_review_at": m.last_review_at,
        "reps": m.reps,
        "lapses": m.lapses,
        "last_lapse_at": m.last_lapse_at,
    }
    if all(getattr(card, k) == v for k, v in new_values.items()):
        return False
    for k, v in new_values.items():
        setattr(card, k, v)
    card.rev += 1
    card.save(update_fields=[*new_values, "rev", "updated_at"])
    return True


# ------------------------------------------------------------------------------------------------------ undo
def undo_review(user_id, undo_id, voids_id, *, now: datetime | None = None) -> UndoResult:
    now = now or timezone.now()
    with transaction.atomic():
        existing = RecallReviewLog.objects.filter(user_id=user_id, id=undo_id).first()
        target = RecallReviewLog.objects.filter(user_id=user_id, id=voids_id, kind="review").first()
        if existing is not None:
            card = RecallCard.objects.filter(user_id=user_id, id=existing.card_id).first()
            return UndoResult(undo_id, existing.voids_id, card, existing=True)
        if target is None:
            raise NotFound("Review not found.")
        eng = load(user_id)
        card = _lock_card(user_id, target.card_id)
        if card is None:
            raise NotFound("Card not found.")
        if RecallReviewLog.objects.filter(user_id=user_id, kind="undo", voids_id=voids_id).exists():
            raise NotUndoable(extra={"reason": "already_undone"})
        if now - target.received_at > timedelta(minutes=lim.UNDO_WINDOW_MINUTES):
            raise NotUndoable(extra={"reason": "too_old"})
        live = RecallReviewLog.objects.filter(user_id=user_id, kind="review").exclude(
            id__in=RecallReviewLog.objects.filter(user_id=user_id, kind="undo").values("voids_id")
        )
        live = live.filter(session_id=target.session_id) if target.session_id else live.filter(session_id__isnull=True)
        recent = list(
            live.order_by("-reviewed_at", "-received_at", "-id").values_list("id", flat=True)[: lim.UNDO_MAX_EVENTS]
        )
        if target.id not in recent:
            raise NotUndoable(extra={"reason": "not_recent"})
        RecallReviewLog.objects.create(
            user_id=user_id,
            id=undo_id,
            kind="undo",
            card_id=card.id,
            item_id=target.item_id,
            item_version_id=target.item_version_id,
            session_id=target.session_id,
            rating=None,
            reviewed_at=now,
            received_at=now,
            mode="normal",
            counts_for_scheduling=False,
            local_date=eng.local_date(now),
            voids_id=target.id,
            flags=[],
        )
        rollups.apply_row(
            user_id,
            local_date=target.local_date,
            chapter_id=card.chapter_id,
            phase_before=target.phase_before,
            rating=target.rating,
            importance=card.importance,
            duration_ms=target.duration_ms,
            sign=-1,
        )
        if target.session_id is not None:
            _session_bump(
                target.session_id,
                sign=-1,
                phase_before=target.phase_before,
                rating=target.rating,
                duration_ms=target.duration_ms,
                now=None,
            )
        with log_guard.replaying():
            RecallReviewLog.objects.filter(user_id=user_id, id=target.id).update(counts_for_scheduling=False)
        replay_card(user_id, card.id, eng=eng, locked=card)
        card.refresh_from_db()
        return UndoResult(undo_id, target.id, card)
