"""
The batch path must equal the one-event path (R2-W0): for any batch, `submit_reviews` leaves the same log rows, card rows,
counters and session totals as applying the same events one by one in time order. Also: replay and idempotency properties.
"""

from __future__ import annotations

import random
import uuid

import pytest
from django.db import connection, transaction
from django.test.utils import CaptureQueriesContext

from modules.recall.models import (
    RecallCard,
    RecallChapterRollup,
    RecallDailyRollup,
    RecallReviewLog,
    RecallSession,
)
from modules.recall.services import reviews
from modules.recall.services.reviews import ReviewIn

from .factories import make_card, make_item, reviewed_fields
from .w5 import BASE, ME, card, days, ev, folded, log_rows, memory_of_row, minutes, rollup_snapshot

pytestmark = pytest.mark.django_db
NOW = days(2)
CARD_FIELDS = (
    "state", "step", "stability", "difficulty", "due_scheduled_at", "postponed_until", "due_at", "last_review_at",
    "reps", "lapses", "last_lapse_at", "rev", "leech", "buried_until", "needs_recheck", "scheduler_version",
)  # fmt: skip
LOG_FIELDS = (
    "kind", "card_id", "rating", "reviewed_at", "received_at", "duration_ms", "mode", "counts_for_scheduling", "local_date",
    "flags", "phase_before", "stability_before", "difficulty_before", "elapsed_days", "retrievability_before", "phase_after",
    "stability_after", "difficulty_after", "scheduled_days", "due_after", "session_id", "item_version_id", "device_id",
    "tz_offset_min", "scheduler_version",
)  # fmt: skip


class _Rollback(Exception):
    pass


def snapshot() -> dict:
    cards = {str(c.id): tuple(getattr(c, f) for f in CARD_FIELDS) for c in RecallCard.objects.filter(user_id=ME)}
    rows = {str(r.id): tuple(getattr(r, f) for f in LOG_FIELDS) for r in RecallReviewLog.objects.filter(user_id=ME)}
    sessions = {
        str(s.id): (s.reviewed, s.new_count, s.again, s.hard, s.good, s.easy, s.active_seconds, s.last_event_at)
        for s in RecallSession.objects.filter(user_id=ME)
    }
    return {"cards": cards, "rows": rows, "sessions": sessions, "rollups": rollup_snapshot()}


def outcome(fn) -> tuple[dict, list]:
    """Run `fn` in a transaction, snapshot the result, then roll everything back so the other path starts equal."""
    try:
        with transaction.atomic():
            statuses = fn()
            snap = snapshot()
            raise _Rollback
    except _Rollback:
        return snap, statuses


def scenario(seed: int):
    rnd = random.Random(seed)
    sessions = [
        RecallSession.objects.create(
            user_id=ME, client_id=uuid.uuid4(), source="today", started_at=BASE, last_event_at=BASE, tz="Asia/Kolkata",
            local_date=BASE.date(),
        )
        for _ in range(2)
    ]  # fmt: skip
    cards: list = []
    for _ in range(rnd.randint(3, 9)):
        kind = rnd.random()
        if kind < 0.25:
            c = make_card(make_item(ME, text=f"Q {uuid.uuid4()}"), ME, **reviewed_fields(rnd.uniform(1, 9)))
        else:
            c = card()
        cards.append(c)
        if rnd.random() < 0.2:  # a sibling card of the same item (buried when this one is reviewed)
            cards.append(make_card(c.item, ME, ordinal=1))
    if rnd.random() < 0.5:
        gone = card()
        RecallCard.objects.filter(pk=gone.pk).update(status="deleted")
        cards.append(gone)
    evs: list[ReviewIn] = []
    for _ in range(rnd.randint(1, 30)):
        c = rnd.choice(cards)
        kw: dict = {}
        roll = rnd.random()
        if roll < 0.08:
            kw["mode"] = "cram"
        elif roll < 0.12:
            kw["rating"] = 7
        if rnd.random() < 0.5:
            kw["session_id"] = rnd.choice([*[s.id for s in sessions], uuid.uuid4()])
        at = minutes(rnd.uniform(-90, 400)) if rnd.random() < 0.9 else days(-40)
        if rnd.random() < 0.05:
            at = days(10)  # in the future: clamped
        evs.append(
            ev(c, kw.pop("rating", rnd.randint(1, 4)), at, duration_ms=rnd.choice([None, 900, 4200, 61000]), **kw)
        )
    if evs and rnd.random() < 0.4:
        evs.append(evs[rnd.randrange(len(evs))])  # the same event twice
    if rnd.random() < 0.2:
        evs.append(ReviewIn(id=uuid.uuid4(), card_id=uuid.uuid4(), rating=3, reviewed_at=minutes(3)))  # unknown card
    return evs


def one_by_one(evs):
    order = sorted(range(len(evs)), key=lambda i: (evs[i].reviewed_at, str(evs[i].id), i))
    out = [None] * len(evs)
    for i in order:
        with transaction.atomic():
            out[i] = reviews.submit_review(ME, evs[i], now=NOW)
    return [(r.status, r.reason) for r in out]


def batched(evs):
    results, _cards = reviews.submit_reviews(ME, evs, now=NOW)
    return [(r.status, r.reason) for r in results]


@pytest.mark.parametrize("seed", range(40))
def test_the_batch_path_equals_the_one_event_path(seed):
    evs = scenario(seed)
    expected, expected_status = outcome(lambda: one_by_one(evs))
    actual, actual_status = outcome(lambda: batched(evs))
    assert actual_status == expected_status
    assert actual["rows"] == expected["rows"]
    assert actual["cards"] == expected["cards"]
    assert actual["sessions"] == expected["sessions"]
    assert actual["rollups"] == expected["rollups"]


def test_a_batch_of_a_hundred_uses_a_fixed_number_of_queries():
    cards_ = [card() for _ in range(100)]
    evs = [ev(c, 3, minutes(i)) for i, c in enumerate(cards_)]
    with CaptureQueriesContext(connection) as q:
        results, _ = reviews.submit_reviews(ME, evs, now=NOW)
    assert [r.status for r in results] == ["applied"] * 100
    assert len(q) <= 40, len(q)  # was about 1400 before the bulk path


def test_the_cards_of_a_bulk_batch_still_equal_the_fold_and_a_replay_changes_nothing():
    cs = [card() for _ in range(6)]
    evs = [
        ev(c, r, minutes(10 * k + i))
        for k in range(4)
        for i, c in enumerate(cs)
        for r in [random.Random(k * 7 + i).randint(1, 4)]
    ]
    for chunk in (evs[:12], evs[12:]):
        reviews.submit_reviews(ME, chunk, now=NOW)
    for c in cs:
        assert memory_of_row(c) == folded(c)
        assert not reviews.replay_card(ME, c.id)


def test_sending_the_same_batch_again_changes_nothing_and_reports_duplicates():
    cs = [card() for _ in range(5)]
    evs = [ev(c, 3, minutes(i)) for i, c in enumerate(cs)]
    reviews.submit_reviews(ME, evs, now=NOW)
    before = snapshot()
    results, _ = reviews.submit_reviews(ME, evs, now=NOW)
    assert [r.status for r in results] == ["duplicate"] * 5
    assert snapshot() == before and log_rows().count() == 5
    assert RecallDailyRollup.objects.get(user_id=ME).good == 5
    assert RecallChapterRollup.objects.filter(user_id=ME).count() <= 1


def test_an_event_older_than_the_cards_newest_review_still_goes_through_the_replay_path():
    c = card()
    reviews.submit_reviews(ME, [ev(c, 3, minutes(50))], now=NOW)
    results, _ = reviews.submit_reviews(ME, [ev(c, 1, minutes(5))], now=NOW)
    assert (results[0].status, results[0].merged) == ("applied", True)
    assert memory_of_row(c) == folded(c)
