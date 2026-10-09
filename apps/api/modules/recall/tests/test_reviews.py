"""Submitting reviews (ERD 3.5): idempotency, late and duplicate events, the fold, clamps, stale content, batches."""

from __future__ import annotations

import random
import uuid
from datetime import timedelta

import pytest

from modules.recall.errors import BatchTooLarge
from modules.recall.models import RecallDailyRollup, RecallItemVersion, RecallSettings
from modules.recall.services import reviews

from .w5 import BASE, ME, card, days, ev, folded, log_rows, memory_of_row, minutes

pytestmark = pytest.mark.django_db
NOW = days(2)


def submit(e, now=NOW):
    return reviews.submit_review(ME, e, now=now)


def test_the_first_review_moves_a_new_card_into_learning_and_fills_the_log_row():
    c = card()
    res = submit(ev(c, 3, minutes(1), duration_ms=4200))
    assert (res.status, res.merged) == ("applied", False)
    c.refresh_from_db()
    assert (c.state, c.reps, c.rev) == (1, 1, 2) and c.due_at > minutes(1) and c.stability is not None
    row = log_rows().get()
    assert (row.phase_before, row.phase_after, row.counts_for_scheduling, row.duration_ms) == (0, 1, True, 4200)
    assert row.due_after == c.due_at and row.scheduler_version == "fsrs-6.0" and row.local_date == BASE.date()
    r = RecallDailyRollup.objects.get(user_id=ME)
    assert (r.new_cards, r.good, r.seconds) == (1, 1, 4)


def test_a_duplicate_event_is_a_no_op():
    c = card()
    e = ev(c, 3, minutes(1))
    submit(e)
    before = memory_of_row(c), c.rev
    again = submit(e)
    assert again.status == "duplicate" and log_rows().count() == 1
    c.refresh_from_db()
    assert (memory_of_row(c), c.rev) == before
    assert RecallDailyRollup.objects.get(user_id=ME).good == 1


def test_a_late_event_is_replayed_into_the_fold():
    c = card()
    submit(ev(c, 3, minutes(60)))
    res = submit(ev(c, 1, minutes(1)))  # arrives after a newer review
    assert res.status == "applied" and res.merged is True
    assert memory_of_row(c) == folded(c)
    first = log_rows().order_by("reviewed_at").first()
    assert first.phase_before == 0 and log_rows().order_by("reviewed_at").last().phase_before == 1


def test_a_reviews_phase_move_by_a_late_event_moves_the_rollup_counts():
    c = card()
    submit(ev(c, 3, minutes(60)))
    submit(ev(c, 3, minutes(1)))
    r = RecallDailyRollup.objects.get(user_id=ME)
    assert (r.new_cards, r.learn_reviews) == (1, 1)


@pytest.mark.parametrize("seed", range(6))
def test_two_devices_rating_one_card_equal_the_fold_in_any_arrival_order(seed):
    c = card()
    rng = random.Random(seed)
    events = [
        ev(c, rng.choice((1, 2, 3, 4)), minutes(10 * i + rng.random()), device_id="phone" if i % 2 else "laptop")
        for i in range(12)
    ]
    rng.shuffle(events)
    for e in events:
        submit(e)
    assert memory_of_row(c) == folded(c)
    assert not reviews.replay_card(ME, c.id)  # replay finds nothing to change


def test_the_clock_skew_clamp():
    c = card()
    res = submit(ev(c, 3, NOW + timedelta(hours=1)))
    assert res.status == "applied"
    row = log_rows().get()
    assert row.reviewed_at == NOW and "clamped_time" in row.flags
    c2 = card()
    submit(ev(c2, 3, NOW + timedelta(minutes=4)))
    assert log_rows(card_id=c2.id).get().flags == []


def test_the_thirty_day_cutoff():
    c = card()
    res = submit(ev(c, 3, NOW - timedelta(days=31)))
    assert res.status == "late_unapplied"
    row = log_rows().get()
    assert not row.counts_for_scheduling and "late" in row.flags
    c.refresh_from_db()
    assert c.state == 0 and c.reps == 0
    ok = card()
    assert submit(ev(ok, 3, NOW - timedelta(days=29))).status == "applied"


def test_a_review_of_a_deleted_card_is_logged_but_changes_nothing():
    c = card(status="deleted")
    res = submit(ev(c, 3, minutes(1)))
    assert res.status == "applied_to_deleted"
    row = log_rows().get()
    assert "deleted_card" in row.flags and not row.counts_for_scheduling
    c.refresh_from_db()
    assert (c.state, c.rev) == (0, 1)
    assert RecallDailyRollup.objects.get(user_id=ME).new_cards == 1


def test_a_review_of_content_that_changed_in_substance_is_stale():
    c = card()
    old = c.item_version
    new = RecallItemVersion.objects.create(
        item=c.item, version_no=2, state="superseded", change_kind="substantive", fields=old.fields, content_hash="x"
    )
    type(c).objects.filter(pk=c.pk).update(item_version=new)
    res = submit(ev(c, 3, minutes(1), item_version_id=old.id))
    assert res.status == "stale_content"
    c.refresh_from_db()
    assert c.needs_recheck and c.state == 0
    row = log_rows().get()
    assert "stale_content" in row.flags and not row.counts_for_scheduling


def test_a_review_of_text_that_only_had_a_typo_fixed_still_counts():
    c = card()
    old = c.item_version
    new = RecallItemVersion.objects.create(
        item=c.item, version_no=2, state="superseded", change_kind="typo", fields=old.fields, content_hash="y"
    )
    type(c).objects.filter(pk=c.pk).update(item_version=new)
    assert submit(ev(c, 3, minutes(1), item_version_id=old.id)).status == "applied"


def test_cram_is_logged_and_counted_in_rollups_but_does_not_schedule():
    c = card()
    submit(ev(c, 3, minutes(1), mode="cram"))
    c.refresh_from_db()
    assert c.state == 0 and not log_rows().get().counts_for_scheduling
    assert RecallDailyRollup.objects.get(user_id=ME).good == 1


def test_review_ahead_schedules_like_a_normal_review():
    c = card()
    submit(ev(c, 3, minutes(1), mode="review_ahead"))
    c.refresh_from_db()
    assert c.state == 1


def test_unknown_and_foreign_cards_and_bad_input_are_invalid_and_write_nothing():
    other = card(owner=uuid.uuid4())
    for e in (ev(other), ev(card(), rating=7), ev(card(), mode="sprint")):
        assert submit(e).status == "invalid"
    assert submit(reviews.ReviewIn(uuid.uuid4(), uuid.uuid4(), 3, BASE)).reason == "unknown_card"
    assert log_rows().count() == 0 and log_rows(user=other.user_id).count() == 0


def test_duration_is_capped():
    c = card()
    submit(ev(c, 3, minutes(1), duration_ms=9_000_000))
    assert log_rows().get().duration_ms == 600_000


def test_the_leech_flag_is_set_at_the_threshold_and_announced_once(django_capture_on_commit_callbacks):
    from core import events

    seen = []
    events.subscribe("recall_leech_detected", lambda **p: seen.append(p))
    RecallSettings.objects.update_or_create(user_id=ME, defaults={"leech_threshold": 4})
    c = card()

    def step(rating, t):
        submit(
            ev(c, rating, minutes(t)), now=minutes(t + 1)
        )  # the clock moves with the review, so nothing is late or clamped
        c.refresh_from_db()

    with django_capture_on_commit_callbacks(execute=True):
        t = 0.0
        for _ in range(4):  # graduate it
            step(3, t)
            t += 30
        for _ in range(5):
            t = (c.due_at - BASE).total_seconds() / 60 + 1
            step(3, t)
            step(1, t + 1)  # a lapse
            t += 2
            for _ in range(3):  # relearn and back to review
                t = (c.due_at - BASE).total_seconds() / 60 + 1
                step(3, t)
    c.refresh_from_db()
    assert c.lapses >= 4 and c.leech
    assert len(seen) == 1 and set(seen[0]) == {"user_id", "card_id", "lapses"}
    events.clear()


def test_siblings_of_a_cloze_are_buried_until_the_end_of_the_study_day():
    first = card()
    from .factories import make_card

    second = make_card(first.item, ME, ordinal=2)
    submit(ev(first, 3, NOW - timedelta(minutes=1)))
    second.refresh_from_db()
    assert second.buried_until is not None and second.buried_until > NOW
    assert second.rev == 2


def test_a_batch_applies_in_time_order_and_one_bad_event_does_not_fail_the_rest():
    c = card()
    good = [ev(c, 3, minutes(2)), ev(c, 2, minutes(1))]
    bad = reviews.ReviewIn(uuid.uuid4(), uuid.uuid4(), 3, BASE)
    results, cards_ = reviews.submit_reviews(ME, [good[0], bad, good[1]], now=NOW)
    assert [r.status for r in results] == ["applied", "invalid", "applied"]
    assert [cc.id for cc in cards_] == [c.id] and memory_of_row(c) == folded(c)


def test_a_batch_of_more_than_a_hundred_is_refused():
    c = card()
    with pytest.raises(BatchTooLarge):
        reviews.submit_reviews(ME, [ev(c, 3, minutes(i)) for i in range(101)], now=NOW)
    assert log_rows().count() == 0
    results, _ = reviews.submit_reviews(ME, [ev(c, 3, minutes(i)) for i in range(100)], now=NOW)
    assert len(results) == 100 and memory_of_row(c) == folded(c)


def test_the_same_event_twice_in_one_batch_counts_once():
    c = card()
    e = ev(c, 3, minutes(1))
    results, _ = reviews.submit_reviews(ME, [e, e], now=NOW)
    assert sorted(r.status for r in results) == ["applied", "duplicate"]
    assert log_rows().count() == 1
