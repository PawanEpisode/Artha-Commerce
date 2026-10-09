"""Undo (a compensating event), rollups that stay equal to a rebuild, and replay that equals the stored state."""

from __future__ import annotations

import random
import uuid
from datetime import timedelta

import pytest
from rest_framework.exceptions import NotFound

from modules.recall.errors import NotUndoable
from modules.recall.models import RecallDailyRollup, RecallSession
from modules.recall.services import reviews, rollups, sessions

from .w5 import ME, card, days, ev, folded, log_rows, memory_of_row, minutes, rollup_snapshot

pytestmark = pytest.mark.django_db
NOW = days(2)


def submit(e, now=NOW):
    return reviews.submit_review(ME, e, now=now)


def undo(voids, now=NOW, undo_id=None):
    return reviews.undo_review(ME, undo_id or uuid.uuid4(), voids, now=now)


def test_undo_puts_the_card_back_and_takes_the_counts_off():
    c = card()
    submit(ev(c, 3, minutes(1)))
    before = memory_of_row(c)
    second = ev(c, 1, minutes(30), duration_ms=3000)
    submit(second)
    res = undo(second.id)
    assert res.card.rev > 1 and memory_of_row(c) == before == folded(c)
    voided = log_rows().get(id=second.id)
    assert not voided.counts_for_scheduling
    undo_row = log_rows(kind="undo").get()
    assert (undo_row.voids_id, undo_row.rating) == (second.id, None)
    r = RecallDailyRollup.objects.get(user_id=ME)
    assert (r.again, r.good, r.seconds, r.learn_reviews, r.new_cards) == (0, 1, 0, 0, 1)


def test_undo_is_idempotent_on_its_own_id_and_a_review_is_undone_once():
    c = card()
    e = ev(c, 3, minutes(1))
    submit(e)
    uid = uuid.uuid4()
    first = undo(e.id, undo_id=uid)
    again = undo(e.id, undo_id=uid)
    assert again.existing and not first.existing and log_rows(kind="undo").count() == 1
    with pytest.raises(NotUndoable) as err:
        undo(e.id)
    assert err.value.extra == {"reason": "already_undone"}


def test_only_the_last_ten_reviews_of_a_session_can_be_undone():
    c = card()
    s, _ = sessions.open_session(ME, uuid.uuid4(), source="today", now=NOW)
    evs = [ev(c, 3, minutes(i), session_id=s.id) for i in range(11)]
    for e in evs:
        submit(e)
    with pytest.raises(NotUndoable) as err:
        undo(evs[0].id)
    assert err.value.extra["reason"] == "not_recent"
    undo(evs[1].id)  # the tenth from the end is still in reach
    s.refresh_from_db()
    assert s.reviewed == 10


def test_undo_needs_the_review_to_be_under_thirty_minutes_old():
    c = card()
    e = ev(c, 3, minutes(1))
    submit(e, now=NOW)
    with pytest.raises(NotUndoable) as err:
        undo(e.id, now=NOW + timedelta(minutes=31))
    assert err.value.extra["reason"] == "too_old"
    undo(e.id, now=NOW + timedelta(minutes=29))


def test_undo_of_unknown_and_other_students_reviews_is_not_found():
    other = uuid.uuid4()
    c = card(owner=other)
    e = ev(c, 3, minutes(1))
    reviews.submit_review(other, e, now=NOW)
    with pytest.raises(NotFound):
        undo(e.id)
    with pytest.raises(NotFound):
        undo(uuid.uuid4())
    assert not log_rows(user=other, kind="undo").exists()


def test_undoing_a_middle_review_replays_the_later_ones():
    c = card()
    a, b, d = ev(c, 3, minutes(1)), ev(c, 3, minutes(40)), ev(c, 3, minutes(100))
    for e in (a, b, d):
        submit(e)
    undo(b.id)
    assert memory_of_row(c) == folded(c)
    assert log_rows().get(id=d.id).phase_before == 1
    assert rollup_snapshot()[0] == _rebuilt()[0]


def _rebuilt():
    rollups.rebuild(ME)
    return rollup_snapshot()


@pytest.mark.parametrize("seed", range(8))
def test_rollups_kept_incrementally_equal_a_rebuild_after_random_sequences(seed):
    rng = random.Random(seed)
    cards_ = [card(importance=i % 3) for i in range(4)]
    s, _ = sessions.open_session(ME, uuid.uuid4(), source="today", now=NOW)
    done = []
    for _ in range(45):
        c = rng.choice(cards_)
        e = ev(
            c,
            rng.choice((1, 2, 3, 4)),
            days(rng.random() * 5),
            mode=rng.choice(("normal",) * 4 + ("cram", "review_ahead")),
            duration_ms=rng.choice((None, 800, 4000)),
            session_id=rng.choice((None, s.id)),
        )
        res = submit(e)
        done.append((e.id, res.status))
        if rng.random() < 0.25:
            try:
                undo(rng.choice(done[-6:])[0])
            except NotUndoable:
                pass
        if rng.random() < 0.1:
            reviews.replay_card(ME, rng.choice(cards_).id)
    incremental = rollup_snapshot()
    for c in cards_:
        assert memory_of_row(c) == folded(c)
    assert incremental == _rebuilt()
    for c in cards_:  # a replay of an already consistent card changes nothing
        assert not reviews.replay_card(ME, c.id)


def test_replay_equals_the_stored_state_and_does_not_touch_rev():
    c = card()
    for i in range(6):
        submit(ev(c, 3 if i % 3 else 1, minutes(i * 90)))
    stored = memory_of_row(c)
    rev = c.rev
    assert reviews.replay_card(ME, c.id) is False
    c.refresh_from_db()
    assert memory_of_row(c) == stored and c.rev == rev


def test_replay_repairs_a_card_row_that_drifted():
    c = card()
    submit(ev(c, 3, minutes(1)))
    submit(ev(c, 3, minutes(40)))
    good = memory_of_row(c)
    type(c).objects.filter(pk=c.pk).update(stability=99.0, reps=77, due_at=days(400), due_scheduled_at=days(400))
    assert reviews.replay_card(ME, c.id) is True
    assert memory_of_row(c) == good


def test_sessions_counters_follow_new_rows_only():
    c = card()
    s, _ = sessions.open_session(ME, uuid.uuid4(), source="today", now=NOW)
    e = ev(c, 4, minutes(1), session_id=s.id, duration_ms=5000)
    submit(e)
    submit(e)
    s = RecallSession.objects.get(pk=s.pk)
    assert (s.reviewed, s.new_count, s.easy, s.active_seconds) == (1, 1, 1, 5)
