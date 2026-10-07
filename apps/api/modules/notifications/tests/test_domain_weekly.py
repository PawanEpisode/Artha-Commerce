"""When the weekly summary is due, which week it covers and whether the week is worth an email (FR-N13)."""

from datetime import UTC, date, datetime, timedelta

import pytest

from modules.notifications.domain.weekly import (
    WeeklyFacts,
    WeeklyVerdict,
    iso_week_key,
    judge_weekly,
    max_lateness,
    next_weekly_at,
    schedule_weekly,
    week_window,
    weekly_local_date,
    worth_sending,
)

IST = "Asia/Kolkata"
NY = "America/New_York"


def utc(*args):
    return datetime(*args, tzinfo=UTC)


def test_next_weekly_is_the_coming_sunday_at_six_in_the_evening():
    # Wednesday 7 Oct 2026; Sunday is 11 Oct; 18:00 IST is 12:30 UTC.
    assert next_weekly_at(utc(2026, 10, 7, 9, 0), IST) == utc(2026, 10, 11, 12, 30)


def test_it_is_strictly_after_now_so_a_week_never_fires_twice():
    due = utc(2026, 10, 11, 12, 30)
    assert next_weekly_at(due, IST) == utc(2026, 10, 18, 12, 30)
    assert next_weekly_at(due - timedelta(seconds=1), IST) == due


def test_on_sunday_before_six_it_is_today_and_after_six_it_is_next_week():
    assert next_weekly_at(utc(2026, 10, 11, 5, 0), IST) == utc(2026, 10, 11, 12, 30)
    assert next_weekly_at(utc(2026, 10, 11, 13, 0), IST) == utc(2026, 10, 18, 12, 30)


def test_the_local_day_decides_not_the_utc_day():
    # 20:00 UTC Saturday is 01:30 Sunday in India: today's 18:00 is still ahead.
    assert next_weekly_at(utc(2026, 10, 10, 20, 0), IST) == utc(2026, 10, 11, 12, 30)


def test_it_keeps_the_local_time_across_daylight_saving():
    before = next_weekly_at(utc(2026, 10, 21, 12, 0), NY)  # Sunday 25 Oct, still summer time
    after = next_weekly_at(utc(2026, 11, 2, 12, 0), NY)  # Sunday 8 Nov, after the clocks went back on 1 Nov
    assert before == utc(2026, 10, 25, 22, 0)  # EDT, UTC-4
    assert after == utc(2026, 11, 8, 23, 0)  # EST, UTC-5


def test_naive_times_are_rejected():
    with pytest.raises(ValueError):
        next_weekly_at(datetime(2026, 10, 7), IST)
    with pytest.raises(ValueError):
        weekly_local_date(datetime(2026, 10, 7), IST)


def test_schedule_is_none_when_the_student_does_not_want_it():
    now = utc(2026, 10, 7, 9, 0)
    assert schedule_weekly(now=now, enabled=False, tz_name=IST) is None
    assert schedule_weekly(now=now, enabled=True, tz_name=IST) == utc(2026, 10, 11, 12, 30)


def test_the_week_belongs_to_the_day_it_fell_due_even_when_the_sweep_is_late():
    assert weekly_local_date(utc(2026, 10, 11, 12, 30), IST) == date(2026, 10, 11)
    assert weekly_local_date(utc(2026, 10, 11, 20, 0), NY) == date(2026, 10, 11)


def test_window_is_the_seven_days_ending_on_the_sunday():
    assert week_window(date(2026, 10, 11)) == (date(2026, 10, 5), date(2026, 10, 11))


def test_iso_week_key_uses_the_iso_year_at_the_edge():
    assert iso_week_key(date(2026, 10, 11)) == "2026-W41"
    assert iso_week_key(date(2027, 1, 3)) == "2026-W53"
    assert iso_week_key(date(2027, 1, 10)) == "2027-W01"


def facts(**changes):
    base = dict(study_seconds=0, active_days=0, streak_days=0, coverage_pct=None, due_for_revision=0, days_to_exam=None)
    return WeeklyFacts(**{**base, **changes})


def test_an_empty_week_is_skipped():
    assert not worth_sending(facts())
    assert not worth_sending(facts(coverage_pct=40.0, days_to_exam=30))


def test_study_time_or_revision_due_makes_a_week_worth_sending():
    assert worth_sending(facts(study_seconds=60))
    assert worth_sending(facts(due_for_revision=2))


def test_a_summary_is_stale_after_its_useful_life():
    due = utc(2026, 10, 11, 12, 30)
    assert max_lateness() == timedelta(hours=24)
    assert judge_weekly(now=due + timedelta(hours=24), due_at=due) is WeeklyVerdict.SEND
    assert judge_weekly(now=due + timedelta(hours=24, seconds=1), due_at=due) is WeeklyVerdict.STALE
