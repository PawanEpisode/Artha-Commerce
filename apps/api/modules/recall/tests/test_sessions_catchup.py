"""Sessions, the idle tick's service, rebalance, vacation and settings."""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest
from rest_framework.exceptions import NotFound

from core import events
from modules.recall.errors import InvalidSetting
from modules.recall.models import RecallCard, RecallScheduleEvent, RecallSettings
from modules.recall.services import catchup, preferences, reviews, sessions

from .w5 import ME, card, days, ev, folded, log_rows, memory_of_row, minutes

pytestmark = pytest.mark.django_db
NOW = days(2)


def test_opening_a_session_is_idempotent_on_the_client_id():
    cid = uuid.uuid4()
    a, created = sessions.open_session(ME, cid, source="today", planned_count=20, now=NOW)
    b, again = sessions.open_session(ME, cid, source="today", now=NOW)
    assert created and not again and a.id == b.id == cid  # reviews can carry the client id before the session is opened
    assert (a.local_date, a.tz, a.planned_count, a.status) == (NOW.date(), "Asia/Kolkata", 20, "open")


@pytest.mark.parametrize(("source", "tz"), [("nonsense", None), ("today", "Mars/Olympus")])
def test_a_bad_source_or_time_zone_is_refused(source, tz):
    with pytest.raises(InvalidSetting):
        sessions.open_session(ME, uuid.uuid4(), source=source, tz=tz, now=NOW)


def test_closing_a_session_summarises_it_and_announces_it_once(django_capture_on_commit_callbacks):
    seen = []
    events.subscribe("recall_session_completed", lambda **p: seen.append(p))
    c = card()
    s, _ = sessions.open_session(ME, uuid.uuid4(), source="chapter", now=NOW)
    for i, rating in enumerate((3, 1, 4)):
        reviews.submit_review(ME, ev(c, rating, minutes(i * 30), session_id=s.id), now=NOW)
    with django_capture_on_commit_callbacks(execute=True):
        row, summary = sessions.close_session(ME, s.id, now=NOW)
        again_row, again = sessions.close_session(ME, s.id, now=NOW)
    assert row.status == "closed" and again_row.status == "closed"
    assert summary["reviewed"] == 3 and summary["ratings"] == {"again": 1, "hard": 0, "good": 1, "easy": 1}
    assert summary["by_chapter"] == [{"chapter_id": None, "reviews": 3, "again": 1}] and summary["streak_after"] == 0
    assert again == summary and len(seen) == 1 and seen[0]["reviewed"] == 3
    events.clear()


def test_closing_someone_elses_session_is_not_found():
    s, _ = sessions.open_session(uuid.uuid4(), uuid.uuid4(), source="today", now=NOW)
    with pytest.raises(NotFound):
        sessions.close_session(ME, s.id)


def test_the_tick_closes_sessions_idle_for_an_hour_and_only_those():
    idle, _ = sessions.open_session(ME, uuid.uuid4(), source="today", now=NOW)
    fresh, _ = sessions.open_session(ME, uuid.uuid4(), source="today", now=NOW + timedelta(minutes=30))
    assert sessions.close_idle(now=NOW + timedelta(minutes=59)) == 0
    assert sessions.close_idle(now=NOW + timedelta(minutes=61)) == 1
    idle.refresh_from_db(), fresh.refresh_from_db()
    assert (idle.status, fresh.status) == ("auto_closed", "open") and idle.ended_at == idle.last_event_at
    assert sessions.close_idle(now=NOW + timedelta(minutes=61)) == 0


def overdue_cards(n):
    out = []
    for i in range(n):
        c = card()
        reviews.submit_review(ME, ev(c, 3, days(-60) + timedelta(minutes=i)), now=days(-60) + timedelta(hours=1))
        for _ in range(3):
            c.refresh_from_db()
            reviews.submit_review(ME, ev(c, 3, c.due_at + timedelta(minutes=1)), now=c.due_at + timedelta(hours=1))
        out.append(c)
    return out


def test_rebalance_keeps_the_daily_limit_today_and_spreads_the_rest():
    RecallSettings.objects.update_or_create(user_id=ME, defaults={"reviews_per_day": 20})
    cs = overdue_cards(30)
    RecallCard.objects.filter(user_id=ME).update(
        due_at=NOW - timedelta(days=5), due_scheduled_at=NOW - timedelta(days=5)
    )
    result = catchup.rebalance(ME, 3, now=NOW)
    assert (result["moved"], result["kept_today"], result["per_day"]) == (10, 20, [10, 0, 0])
    moved = RecallCard.objects.filter(user_id=ME, postponed_until__isnull=False)
    assert moved.count() == 10 and all(c.due_at == c.postponed_until > NOW for c in moved)
    events_ = RecallScheduleEvent.objects.filter(kind="postpone", reason_code="rebalance")
    assert events_.count() == 10 and events_.first().ref.startswith("rebalance:")
    for c in cs:  # the fold sees the same postponement the card row carries
        assert memory_of_row(c)["postponed_until"] == folded(c)["postponed_until"]
    assert catchup.rebalance(ME, 3, now=NOW)["moved"] == 0  # nothing left over the limit


def test_rebalance_never_moves_a_mandatory_card_that_is_slipping():
    RecallSettings.objects.update_or_create(user_id=ME, defaults={"reviews_per_day": 20})
    overdue_cards(25)
    mandatory = card(importance=2)
    reviews.submit_review(ME, ev(mandatory, 3, days(-60)), now=days(-60) + timedelta(hours=1))
    RecallCard.objects.filter(user_id=ME).update(
        due_at=NOW - timedelta(days=5), due_scheduled_at=NOW - timedelta(days=5)
    )
    catchup.rebalance(ME, 7, now=NOW)
    mandatory.refresh_from_db()
    assert mandatory.postponed_until is None


def test_vacation_postpones_what_falls_due_and_ending_it_brings_it_back():
    c = card()
    reviews.submit_review(ME, ev(c, 3, days(0)), now=NOW)
    due = RecallCard.objects.get(pk=c.pk).due_at
    until = (NOW + timedelta(days=5)).date()
    out = preferences.set_vacation(ME, until, now=NOW)
    assert out["postponed"] == 1
    c.refresh_from_db()
    assert c.due_at > NOW + timedelta(days=5) and c.postponed_until == c.due_at
    assert RecallSettings.objects.get(user_id=ME).vacation_until == until
    assert memory_of_row(c) == folded(c)
    back = preferences.set_vacation(ME, None, now=NOW + timedelta(days=1))
    c.refresh_from_db()
    assert back["restored"] == 1 and c.postponed_until is None and c.due_at == due
    assert memory_of_row(c) == folded(c)


@pytest.mark.parametrize("until", [date(2026, 10, 1), date(2027, 3, 1)])
def test_vacation_dates_are_limited_to_the_next_sixty_days(until):
    with pytest.raises(InvalidSetting):
        preferences.set_vacation(ME, until, now=NOW)


def test_settings_are_validated_and_saved():
    row = preferences.update_settings(
        ME,
        {
            "new_per_day": 15,
            "desired_retention": 0.92,
            "learning_steps_min": [2, 20],
            "tz": "Asia/Dubai",
            "improve_scheduler_consent": True,
        },
        now=NOW,
    )
    assert (row.new_per_day, row.desired_retention, row.learning_steps_min, row.tz) == (
        15,
        Decimal("0.92"),
        [2, 20],
        "Asia/Dubai",
    )
    assert row.improve_scheduler_consent and row.consent_at == NOW


@pytest.mark.parametrize(
    "bad",
    [
        {"desired_retention": 0.5},
        {"desired_retention": "high"},
        {"new_per_day": 101},
        {"new_per_day": True},
        {"reviews_per_day": 19},
        {"learning_steps_min": [1, 2, 3, 4, 5]},
        {"learning_steps_min": [0]},
        {"relearning_steps_min": [10, 20, 30, 40]},
        {"tz": "Nowhere/Land"},
        {"day_start_hour": 7},
        {"catchup_mode": "maybe"},
        {"bury_siblings": "yes"},
        {"max_interval_days": 10},
    ],
)
def test_bad_settings_are_refused_with_the_field_named_and_nothing_is_saved(bad):
    with pytest.raises(InvalidSetting) as err:
        preferences.update_settings(ME, {**bad, "new_per_day": 12} if "new_per_day" not in bad else bad)
    assert err.value.extra["errors"][0]["field"] == next(iter(bad))
    assert RecallSettings.objects.filter(user_id=ME, new_per_day=12).count() == 0


def test_changing_retention_never_reschedules_a_card():
    c = card()
    reviews.submit_review(ME, ev(c, 3, days(0)), now=NOW)
    for _ in range(3):
        c.refresh_from_db()
        reviews.submit_review(ME, ev(c, 3, c.due_at + timedelta(minutes=1)), now=NOW + timedelta(days=60))
    c.refresh_from_db()
    before, rev = memory_of_row(c), c.rev
    preferences.update_settings(ME, {"desired_retention": 0.97, "max_interval_days": 60, "learning_steps_min": [5]})
    c.refresh_from_db()
    assert (memory_of_row(c), c.rev) == (before, rev)
    assert log_rows().count() == 4
