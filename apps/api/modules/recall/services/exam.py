"""
Exam horizon upkeep (R2-W1): re-evaluate the effective due of a student's cards against her exam date. The review service
applies the horizon to the card it just wrote; this catches everything else (a changed exam date, a card postponed or
unpostponed, the nightly passing of time, an exam that has now passed). Only `due_at` moves; the scheduler's own date and the
log are never touched. Idempotent: a second run changes nothing. No card text, ids and numbers only.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

from django.db.models import F, Q
from django.utils import timezone

from ..domain import limits as lim
from ..domain.folding import CardState, effective_due
from ..domain.fsrs6 import MemoryState
from ..models import RecallCard, RecallScheduleEvent
from . import engine

logger = logging.getLogger(__name__)
CHUNK = 500


def _base_due(card: RecallCard) -> datetime | None:
    state = CardState(MemoryState(card.state), card.due_scheduled_at, card.postponed_until)
    return effective_due(state)


def reevaluate_student(user_id, *, now: datetime | None = None) -> int:
    """Returns how many cards changed their effective due."""
    now = now or timezone.now()
    eng = engine.load(user_id)
    cutoff = (eng.exam_at - timedelta(days=lim.EXAM_WINDOW_END_DAYS)) if eng.exam_at else now
    # Candidates: cards whose own date lies beyond the cutoff (they may need pulling in) and cards whose stored due differs from
    # their own date (moved before, postponed, or restored): everything else cannot change
    qs = RecallCard.objects.filter(
        user_id=user_id, status="active", deleted_at__isnull=True, state__gt=0, due_scheduled_at__isnull=False
    ).filter(Q(due_scheduled_at__gt=cutoff) | Q(postponed_until__gt=cutoff) | ~Q(due_at=F("due_scheduled_at")))
    changed = 0
    audit: list[RecallScheduleEvent] = []
    for card in qs.order_by("id").iterator(chunk_size=CHUNK):
        new = eng.horizon(card.id, _base_due(card), card.last_review_at, now)
        if new == card.due_at:
            continue
        updated = RecallCard.objects.filter(pk=card.pk, rev=card.rev).update(
            due_at=new, rev=F("rev") + 1, updated_at=now
        )
        if not updated:  # changed by a review meanwhile; that write applied the horizon itself
            continue
        changed += 1
        audit.append(
            RecallScheduleEvent(
                user_id=user_id,
                card_id=card.pk,
                kind="horizon",
                at=now,
                from_due=card.due_at,
                to_due=new,
                reason_code="exam_horizon",
                ref=f"horizon:{now.date().isoformat()}",
            )
        )
        if len(audit) >= CHUNK:
            RecallScheduleEvent.objects.bulk_create(audit)
            audit = []
    if audit:
        RecallScheduleEvent.objects.bulk_create(audit)
    if changed:
        logger.info("recall exam horizon re-evaluated", extra={"cards_changed": changed})
    return changed
