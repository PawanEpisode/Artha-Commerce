from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest

from modules.recall.domain import scheduling as sc


def test_priority_prefers_important_and_overdue_with_a_cap():
    assert sc.priority(2, 0.5, 0) > sc.priority(1, 0.5, 0) > sc.priority(0, 0.5, 0)
    assert sc.priority(0, 0.9, 10) > sc.priority(0, 0.9, 1)
    assert sc.priority(0, 0.9, 30) == sc.priority(0, 0.9, 900)


def test_days_to_clear_and_catchup_rules():
    assert sc.days_to_clear(0, 100) == 0
    assert sc.days_to_clear(250, 100) == 3
    assert sc.days_to_clear(10**6, 100) == 60
    assert not sc.catchup_state(150, 1, 100).active
    assert sc.catchup_state(201, 1, 100).active  # more than twice the limit
    assert sc.catchup_state(150, 4, 100).active  # oldest over 3 days with more than one day of work
    assert not sc.catchup_state(80, 9, 100).active  # old but only a day of work
    assert sc.catchup_state(5, 0, 100, "on").active
    assert not sc.catchup_state(500, 9, 100, "off").active


def test_study_day_uses_the_students_zone_and_start_hour():
    tz = "Asia/Kolkata"
    late = datetime(2026, 3, 2, 21, 30, tzinfo=UTC)  # 03:00 on 3 March in India, before a 04:00 day start
    assert sc.local_date_of(late, tz, 4) == date(2026, 3, 2)
    assert sc.local_date_of(late, tz, 0) == date(2026, 3, 3)
    assert sc.end_of_study_day(late, tz, 4).astimezone(UTC) == datetime(2026, 3, 2, 22, 30, tzinfo=UTC)


def test_forgotten_score_and_streak_and_forecast():
    assert sc.is_forgotten(1, 0)
    assert sc.is_forgotten(0, 2)
    assert not sc.is_forgotten(0, 1)
    today = date(2026, 3, 10)
    days = {today - timedelta(days=i): 6 for i in range(1, 4)}
    assert sc.streak(days, today) == 3  # today not yet done: yesterday's run still counts
    days[today] = 5
    assert sc.streak(days, today) == 4
    days[today - timedelta(days=2)] = 4
    assert sc.streak(days, today) == 2
    assert sc.forecast(
        [today - timedelta(days=3), today, today + timedelta(days=2), today + timedelta(days=40), None], today, 5
    ) == [2, 0, 1, 0, 0]


def test_review_ahead_takes_the_weakest_not_yet_due():
    now = datetime(2026, 3, 10, tzinfo=UTC)

    def c(i, stab, last):
        return sc.CardView(i, "A", 0, 2, stab, now - timedelta(days=last), now + timedelta(days=2))

    got = sc.review_ahead([c("strong", 100.0, 1), c("weak", 2.0, 5), c("mid", 10.0, 5)], now, 0.15, size=2)
    assert got == ("weak", "mid")


def test_r2_stubs_are_not_implemented():
    for fn in (sc.horizon, sc.r_exam, sc.quick_set, sc.pacing):
        with pytest.raises(NotImplementedError):
            fn()
