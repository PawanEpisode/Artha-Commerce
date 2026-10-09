"""Builders for the review tests: a student (the one the `api` fixture signs in as), cards, events and table snapshots."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from modules.coverage.tests.conftest import USER as ME
from modules.recall.models import RecallChapterRollup, RecallDailyRollup, RecallReviewLog
from modules.recall.services import engine
from modules.recall.services.reviews import ReviewIn

from .factories import make_card, make_item

BASE = datetime(2026, 10, 9, 8, 0, tzinfo=UTC)
DAILY = (
    "new_cards",
    "learn_reviews",
    "review_reviews",
    "relearn_reviews",
    "again",
    "hard",
    "good",
    "easy",
    "mandatory_reviews",
    "seconds",
)


def card(owner=ME, **extra):
    return make_card(make_item(owner, text=f"Question {uuid.uuid4()}?"), owner, **extra)


def ev(c, rating=3, at=BASE, **kw) -> ReviewIn:
    return ReviewIn(id=kw.pop("id", uuid.uuid4()), card_id=c.id, rating=rating, reviewed_at=at, **kw)


def minutes(n: float) -> datetime:
    return BASE + timedelta(minutes=n)


def days(n: float) -> datetime:
    return BASE + timedelta(days=n)


def log_rows(user=ME, **flt):
    return RecallReviewLog.objects.filter(user_id=user, **flt)


def rollup_snapshot(user=ME):
    """Both counter tables without the all-zero rows an undo leaves behind (a rebuild never creates them)."""
    daily = {}
    for r in RecallDailyRollup.objects.filter(user_id=user):
        vals = tuple(getattr(r, f) for f in DAILY)
        if any(vals):
            daily[r.local_date] = vals
    chap = {}
    for r in RecallChapterRollup.objects.filter(user_id=user):
        vals = (r.reviews, r.again, r.mandatory_reviews)
        if any(vals):
            chap[(r.local_date, r.chapter_id)] = vals
    return daily, chap


MEMORY_COLUMNS = (
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
)


def memory_of_row(c) -> dict:
    c.refresh_from_db()
    return {k: getattr(c, k) for k in MEMORY_COLUMNS}


def folded(c, user=ME) -> dict:
    """What the pure fold says the card should be, from the log and the schedule events."""
    from modules.recall.domain.folding import ReviewEvent, ScheduleEvent, effective_due, fold
    from modules.recall.models import RecallScheduleEvent

    eng = engine.load(user)
    voided = set(RecallReviewLog.objects.filter(user_id=user, kind="undo").values_list("voids_id", flat=True))
    facts = [
        ReviewEvent(str(r.id), r.reviewed_at, r.rating, r.counts_for_scheduling, r.id in voided)
        for r in log_rows(user, card_id=c.id, kind="review")
    ]
    facts += [ScheduleEvent(str(e.id), e.at, e.kind, e.to_due) for e in RecallScheduleEvent.objects.filter(card=c)]
    st = fold(facts, eng.weights, eng.cfg, card_id=c.id)
    m = st.memory
    return {
        "state": m.phase,
        "step": m.step,
        "stability": m.stability,
        "difficulty": m.difficulty,
        "due_scheduled_at": st.due_scheduled_at,
        "postponed_until": st.postponed_until,
        "due_at": effective_due(st),
        "last_review_at": m.last_review_at,
        "reps": m.reps,
        "lapses": m.lapses,
        "last_lapse_at": m.last_lapse_at,
    }
