"""R2-W1: the exam horizon and the retention boost as the review service applies them (engine, fast path, replay, settings)."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest

from modules.coverage.models import Enrollment
from modules.recall.models import RecallSettings
from modules.recall.services import engine, reviews

from .factories import make_card, make_item
from .w5 import ME, days, ev, memory_of_row

pytestmark = pytest.mark.django_db
NOW = days(2)  # 2026-10-11 08:00 UTC
EXAM_DAY = date(2026, 11, 20)  # 40 days out
EXAM_AT = datetime(2026, 11, 20, 4, 0, tzinfo=UTC) - timedelta(hours=5, minutes=30)  # 04:00 in Asia/Kolkata


def enrol(scheme, exam=EXAM_DAY):
    return Enrollment.objects.create(user_id=ME, scheme=scheme, level=scheme.level, exam_date=exam)


def seasoned(importance=1, stability=200.0):
    """A card reviewed 20 days ago with a long memory, so a Good review today lands far beyond the exam."""
    last = NOW - timedelta(days=20)
    item = make_item(ME, text=f"Q {importance} {stability}")
    return make_card(
        item,
        ME,
        importance=importance,
        state=2,
        stability=stability,
        difficulty=5.0,
        reps=4,
        last_review_at=last,
        due_scheduled_at=NOW,
        due_at=NOW,
    )


def rate(c, rating=3, at=NOW):
    return reviews.submit_review(ME, ev(c, rating, at), now=NOW)


def test_the_engine_reads_the_exam_from_the_active_enrolment(scheme):
    assert engine.load(ME).exam_at is None
    enrol(scheme)
    assert engine.load(ME).exam_at == EXAM_AT


def test_a_review_that_lands_after_the_exam_is_pulled_into_the_final_window(scheme):
    enrol(scheme)
    c = seasoned()
    rate(c)
    c.refresh_from_db()
    assert c.due_scheduled_at > EXAM_AT + timedelta(days=30)  # the scheduler's own date is untouched
    assert EXAM_AT - timedelta(days=7) <= c.due_at <= EXAM_AT - timedelta(days=3)
    assert c.due_at < c.due_scheduled_at


def test_with_the_setting_off_or_without_an_exam_nothing_moves(scheme):
    c = seasoned()
    rate(c)
    c.refresh_from_db()
    assert c.due_at == c.due_scheduled_at  # no enrolment, no exam
    enrol(scheme)
    RecallSettings.objects.update_or_create(user_id=ME, defaults={"exam_horizon": False})
    d = seasoned(stability=201.0)
    rate(d)
    d.refresh_from_db()
    assert d.due_at == d.due_scheduled_at


def test_the_replay_of_a_card_equals_the_fast_path_with_an_exam(scheme):
    enrol(scheme)
    c = seasoned(importance=2, stability=40.0)
    rate(c, 3, NOW)
    rate(c, 3, NOW + timedelta(days=9))  # a second review inside the last 30 days
    before = memory_of_row(c)
    assert reviews.replay_card(ME, c.id, now=NOW + timedelta(days=9)) is False
    assert memory_of_row(c) == before


def test_mandatory_cards_get_a_shorter_interval_than_important_ones_in_the_last_thirty_days(scheme):
    enrol(scheme)
    when = NOW + timedelta(days=15)  # 25 days before the exam
    a, b = seasoned(importance=2, stability=30.0), seasoned(importance=1, stability=30.0)
    for card in (a, b):
        reviews.submit_review(ME, ev(card, 3, when), now=when)
        card.refresh_from_db()
    assert a.due_scheduled_at - when < b.due_scheduled_at - when  # 0.95 retention schedules sooner than 0.90
    assert engine.load(ME).cfg_at(2, NOW).desired_retention == 0.90  # outside the last 30 days: the student's own


def grown(rounds=4, start_days=-170):
    """A card with a real log: Good at each due date from `start_days`, so a replay rebuilds the same memory."""
    c = make_card(make_item(ME, text="grown"), ME, importance=1)
    at = NOW + timedelta(days=start_days)
    for _ in range(rounds):
        reviews.submit_review(ME, ev(c, 3, at), now=at)
        c.refresh_from_db()
        at = c.due_at
    return c, at


def test_changing_the_exam_date_changes_the_materialised_due_on_the_next_replay(scheme):
    enr = enrol(scheme)
    c, _ = grown()
    at = NOW
    reviews.submit_review(ME, ev(c, 3, at), now=at)
    c.refresh_from_db()
    assert c.due_scheduled_at > EXAM_AT  # the real scheduler date is after the exam
    first = c.due_at
    assert reviews.replay_card(ME, c.id, now=at) is False  # replay equals the fast path
    enr.exam_date = EXAM_DAY + timedelta(days=60)
    enr.save()
    assert reviews.replay_card(ME, c.id, now=at) is True
    c.refresh_from_db()
    assert c.due_at != first
