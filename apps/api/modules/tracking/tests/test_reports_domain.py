from datetime import date

import pytest

from modules.tracking.domain import reports as r

MON, SUN = date(2026, 10, 5), date(2026, 10, 4)


def test_week_start_monday_and_sunday():
    assert r.week_start_of(date(2026, 10, 7), 1) == MON
    assert r.week_start_of(SUN, 1) == date(2026, 9, 28)  # Sunday belongs to the week that began on the previous Monday
    assert r.week_start_of(date(2026, 10, 7), 0) == SUN
    assert r.week_start_of(SUN, 0) == SUN
    assert r.week_start_of(MON, 1) == MON


def test_bucket_bounds():
    assert r.bucket_start(date(2026, 10, 17), "month") == date(2026, 10, 1)
    assert r.bucket_end(date(2026, 10, 1), "month") == date(2026, 10, 31)
    assert r.bucket_end(date(2026, 12, 1), "month") == date(2026, 12, 31)
    assert r.bucket_end(date(2028, 2, 1), "month") == date(2028, 2, 29)
    assert r.bucket_end(MON, "week") == date(2026, 10, 11)
    with pytest.raises(r.RangeError):
        r.bucket_start(MON, "year")


def test_buckets_cover_the_range_including_empty_ones():
    weeks = r.buckets(date(2026, 10, 1), date(2026, 10, 31), "week", 1)
    assert [b.start for b in weeks][0] == date(2026, 9, 28) and len(weeks) == 5
    assert all((b.end - b.start).days == 6 for b in weeks)
    months = r.buckets(date(2026, 9, 15), date(2026, 11, 2), "month")
    assert [b.start for b in months] == [date(2026, 9, 1), date(2026, 10, 1), date(2026, 11, 1)]
    assert len(r.buckets(date(2026, 10, 1), date(2026, 10, 7), "day")) == 7
    sunday_weeks = r.buckets(date(2026, 10, 1), date(2026, 10, 31), "week", 0)
    assert sunday_weeks[0].start == date(2026, 9, 27)


def test_range_limits():
    r.validate_range(date(2026, 1, 1), date(2026, 12, 31), "day")  # 365 days
    with pytest.raises(r.RangeError) as e:
        r.validate_range(date(2025, 1, 1), date(2026, 12, 31), "day")
    assert e.value.code == "range_too_long"
    r.validate_range(date(2022, 1, 1), date(2026, 12, 31), "week")
    with pytest.raises(r.RangeError):
        r.validate_range(date(2026, 10, 5), date(2026, 10, 4))


def test_previous_range_has_equal_length():
    assert r.previous_range(date(2026, 10, 5), date(2026, 10, 11)) == (date(2026, 9, 28), date(2026, 10, 4))
    assert r.previous_range(date(2026, 10, 1), date(2026, 10, 1)) == (date(2026, 9, 30), date(2026, 9, 30))


def test_change_reports_seconds_and_percent():
    assert r.change(72000, 90000) == {"seconds": -18000, "percent": -20}
    assert r.change(100, 0) == {"seconds": 100, "percent": None}


@pytest.mark.parametrize(
    ("seconds", "level"),
    [
        (0, 0),
        (1, 1),
        (1799, 1),
        (1800, 2),
        (5399, 2),
        (5400, 3),
        (10799, 3),
        (10800, 4),
        (17999, 4),
        (18000, 5),
        (86400, 5),
    ],
)
def test_heatmap_intensity_edges(seconds, level):
    assert r.intensity(seconds) == level


def test_pace_is_linear_over_seven_days_with_a_fifteen_minute_tolerance():
    assert r.expected_by_today(35 * 60, 2) == 10 * 3600
    assert r.pace(10 * 3600, 35 * 60, 2)["state"] == "on_track"
    assert r.pace(9 * 3600, 35 * 60, 2) == {"expected_seconds": 36000, "gap_seconds": -3600, "state": "behind"}
    assert r.pace(11 * 3600, 35 * 60, 2)["state"] == "ahead"
    assert r.pace(0, 35 * 60, 0)["state"] == "on_track"  # Monday morning
    assert r.pace(36000 - 900, 35 * 60, 2)["state"] == "on_track"  # exactly at the tolerance


def test_streak_counts_back_from_today_or_yesterday():
    met = {date(2026, 10, 3), date(2026, 10, 4), date(2026, 10, 5)}
    assert r.streak(met, MON) == 3
    assert r.streak({date(2026, 10, 3), date(2026, 10, 4)}, MON) == 2  # today still open
    assert r.streak({date(2026, 10, 1)}, MON) == 0
    assert r.streak(set(), MON) == 0


def test_chapter_flags():
    assert r.chapter_flag(6 * 3600, 20, 3600) == "high_time_low_coverage"
    assert r.chapter_flag(600, 10, 3600) == "low_time_low_coverage"
    assert r.chapter_flag(3600, 80, 3600) == ""
    assert r.chapter_flag(2400, 10, 3600) == ""
    assert r.chapter_flag(100, 0, 0) == ""
