"""Reviews under real concurrency and the log's append-only promise. Needs PostgreSQL; skipped on SQLite."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import pytest
from django.db import DatabaseError, close_old_connections, connection, transaction

from modules.recall.models import RecallDailyRollup, RecallReviewLog
from modules.recall.services import log_guard, reviews

from .w5 import ME, card, days, ev, folded, log_rows, memory_of_row, minutes

pytestmark = [
    pytest.mark.django_db(transaction=True, serialized_rollback=True),
    pytest.mark.skipif(connection.vendor != "postgresql", reason="concurrency and triggers need PostgreSQL"),
]
NOW = days(2)


@pytest.fixture(autouse=True)
def _empty_log():
    """The log is an unmanaged table, so the flush between transactional tests does not clear it."""

    def wipe():
        with transaction.atomic(), log_guard.erasing():
            RecallReviewLog.objects.all().delete()

    wipe()
    yield
    wipe()


def race(fns):
    def run(fn):
        close_old_connections()
        try:
            return fn()
        finally:
            connection.close()

    with ThreadPoolExecutor(max_workers=len(fns)) as pool:
        return list(pool.map(run, fns))


def test_two_requests_rating_one_card_at_once_both_land_and_equal_the_fold():
    c = card()
    a, b = ev(c, 3, minutes(1), device_id="phone"), ev(c, 1, minutes(2), device_id="laptop")
    res = race([lambda: reviews.submit_review(ME, a, now=NOW), lambda: reviews.submit_review(ME, b, now=NOW)])
    assert sorted(r.status for r in res) == ["applied", "applied"]
    assert log_rows().count() == 2 and memory_of_row(c) == folded(c)
    r = RecallDailyRollup.objects.get(user_id=ME)
    assert (r.new_cards, r.learn_reviews, r.again, r.good) == (1, 1, 1, 1)


def test_the_same_event_sent_by_many_requests_counts_once():
    c = card()
    e = ev(c, 3, minutes(1))
    res = race([lambda: reviews.submit_review(ME, e, now=NOW) for _ in range(8)])
    assert sorted(r.status for r in res).count("applied") == 1 and log_rows().count() == 1
    assert RecallDailyRollup.objects.get(user_id=ME).good == 1


def test_two_batch_syncs_with_overlapping_ids_do_not_deadlock_or_double_count():
    cards_ = [card() for _ in range(4)]
    shared = [ev(c, 3, minutes(i)) for i, c in enumerate(cards_)]
    mine = [ev(c, 2, minutes(10 + i)) for i, c in enumerate(cards_)]
    theirs = [ev(c, 4, minutes(20 + i)) for i, c in enumerate(cards_)]
    one = shared + mine
    two = list(reversed(shared)) + theirs  # a different card order, the deadlock recipe
    race([lambda: reviews.submit_reviews(ME, one, now=NOW), lambda: reviews.submit_reviews(ME, two, now=NOW)])
    assert log_rows().count() == 12
    for c in cards_:
        assert memory_of_row(c) == folded(c) and not reviews.replay_card(ME, c.id)
    r = RecallDailyRollup.objects.get(user_id=ME)
    assert r.new_cards + r.learn_reviews + r.review_reviews + r.relearn_reviews == 12


def test_the_log_stays_append_only_and_a_replay_may_rewrite_only_derived_columns():
    c = card()
    e = ev(c, 3, minutes(1))
    reviews.submit_review(ME, e, now=NOW)
    with pytest.raises(DatabaseError), transaction.atomic():
        RecallReviewLog.objects.filter(user_id=ME, id=e.id).update(rating=1)
    with pytest.raises(DatabaseError), transaction.atomic():
        RecallReviewLog.objects.filter(user_id=ME, id=e.id).delete()
    with pytest.raises(DatabaseError), transaction.atomic():
        RecallReviewLog.objects.filter(user_id=ME, id=e.id).update(
            stability_after=3.0
        )  # derived, but only under replay
    reviews.submit_review(ME, ev(c, 3, minutes(0)), now=NOW)  # late event: the replay path rewrites derived columns
    assert memory_of_row(c) == folded(c)
    with log_guard.replaying(), pytest.raises(DatabaseError), transaction.atomic():
        RecallReviewLog.objects.filter(user_id=ME, id=e.id).update(reviewed_at=NOW)  # a fact never changes
