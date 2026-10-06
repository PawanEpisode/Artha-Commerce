from datetime import UTC, datetime, time

import pytest

from modules.notifications.domain.nudge import next_nudge_at
from modules.notifications.domain.quiet_hours import (
    in_quiet_hours,
    is_valid_timezone,
    local_date,
    local_day_bounds,
    quiet_window_end,
)

IST = "Asia/Kolkata"


def utc(*args):
    return datetime(*args, tzinfo=UTC)


def test_timezone_validation():
    assert is_valid_timezone(IST)
    assert not is_valid_timezone("Mars/Base")
    assert not is_valid_timezone("")


def test_local_date_crosses_midnight_with_the_zone():
    now = utc(2026, 3, 1, 20, 0)  # 01:30 on 2 March in India
    assert str(local_date(now, IST)) == "2026-03-02"
    assert str(local_date(now, "UTC")) == "2026-03-01"


def test_local_day_bounds_are_utc_instants_of_local_midnights():
    start, end = local_day_bounds(utc(2026, 3, 1, 20, 0), IST)
    assert start == utc(2026, 3, 1, 18, 30) and end == utc(2026, 3, 2, 18, 30)


def test_quiet_hours_across_midnight():
    start, end = time(22, 0), time(7, 0)
    assert in_quiet_hours(utc(2026, 3, 1, 17, 0), IST, start, end)  # 22:30 local
    assert in_quiet_hours(utc(2026, 3, 1, 21, 0), IST, start, end)  # 02:30 local
    assert not in_quiet_hours(utc(2026, 3, 1, 5, 0), IST, start, end)  # 10:30 local
    assert not in_quiet_hours(utc(2026, 3, 1, 1, 30), IST, start, end)  # 07:00 local exactly (end exclusive)


def test_quiet_hours_same_day_window():
    start, end = time(13, 0), time(15, 0)
    assert in_quiet_hours(utc(2026, 3, 1, 8, 30), IST, start, end)
    assert not in_quiet_hours(utc(2026, 3, 1, 4, 0), IST, start, end)


def test_quiet_window_end_is_next_local_end_or_none_outside():
    start, end = time(22, 0), time(7, 0)
    assert quiet_window_end(utc(2026, 3, 1, 17, 0), IST, start, end) == utc(2026, 3, 2, 1, 30)
    assert quiet_window_end(utc(2026, 3, 1, 21, 0), IST, start, end) == utc(2026, 3, 2, 1, 30)
    assert quiet_window_end(utc(2026, 3, 1, 5, 0), IST, start, end) is None


def test_next_nudge_is_today_if_ahead_else_tomorrow():
    assert next_nudge_at(utc(2026, 3, 1, 2, 0), IST, time(10, 0)) == utc(2026, 3, 1, 4, 30)
    assert next_nudge_at(utc(2026, 3, 1, 6, 0), IST, time(10, 0)) == utc(2026, 3, 2, 4, 30)


def test_next_nudge_is_strictly_after_now():
    assert next_nudge_at(utc(2026, 3, 1, 4, 30), IST, time(10, 0)) == utc(2026, 3, 2, 4, 30)


def test_next_nudge_keeps_local_time_across_dst():
    ny = "America/New_York"  # clocks go forward on 8 March 2026
    before = next_nudge_at(utc(2026, 3, 7, 12, 0), ny, time(10, 0))
    after = next_nudge_at(utc(2026, 3, 8, 20, 0), ny, time(10, 0))
    assert before == utc(2026, 3, 7, 15, 0)  # EST, UTC-5
    assert after == utc(2026, 3, 9, 14, 0)  # EDT, UTC-4


def test_naive_now_is_rejected():
    with pytest.raises(ValueError):
        next_nudge_at(datetime(2026, 3, 1), IST, time(10, 0))
