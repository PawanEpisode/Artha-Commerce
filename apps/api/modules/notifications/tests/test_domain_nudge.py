"""When the daily nudge is due: the student's local time, DST, zone and time changes, lateness (FR-N10, FR-N33)."""

from datetime import UTC, date, datetime, time, timedelta

import pytest

from modules.notifications.domain.catalogue import get_event
from modules.notifications.domain.nudge import (
    NudgeVerdict,
    judge_nudge,
    max_lateness,
    next_nudge_at,
    nudge_local_date,
    schedule_nudge,
)

IST = "Asia/Kolkata"
NY = "America/New_York"  # clocks forward 8 March 2026 (02:00 to 03:00) and back 1 November 2026 (02:00 to 01:00)
SYDNEY = "Australia/Sydney"  # southern hemisphere: clocks forward on 4 October 2026, back on 4 April 2027
LONDON = "Europe/London"  # clocks back on 25 October 2026


def utc(*args):
    return datetime(*args, tzinfo=UTC)


# --- next nudge ---------------------------------------------------------------------------------------------------


def test_next_nudge_is_today_when_ahead_else_tomorrow():
    assert next_nudge_at(utc(2026, 10, 7, 2, 0), IST, time(10, 0)) == utc(2026, 10, 7, 4, 30)
    assert next_nudge_at(utc(2026, 10, 7, 6, 0), IST, time(10, 0)) == utc(2026, 10, 8, 4, 30)


def test_it_is_strictly_after_now_so_a_nudge_never_fires_twice_for_one_instant():
    due = utc(2026, 10, 7, 4, 30)
    assert next_nudge_at(due, IST, time(10, 0)) == utc(2026, 10, 8, 4, 30)
    assert next_nudge_at(due - timedelta(seconds=1), IST, time(10, 0)) == due


def test_the_local_day_decides_not_the_utc_day():
    # 23:00 UTC on 7 Oct is already 04:30 on 8 Oct in India: today's 10:00 is still ahead.
    assert next_nudge_at(utc(2026, 10, 7, 23, 0), IST, time(10, 0)) == utc(2026, 10, 8, 4, 30)
    # 02:00 UTC on 7 Oct is 22:00 on 6 Oct in New York (EDT): the next 10:00 is that morning's, 14:00 UTC on the 7th.
    assert next_nudge_at(utc(2026, 10, 7, 2, 0), NY, time(10, 0)) == utc(2026, 10, 7, 14, 0)


def test_naive_times_are_rejected():
    with pytest.raises(ValueError):
        next_nudge_at(datetime(2026, 10, 7), IST, time(10, 0))
    with pytest.raises(ValueError):
        nudge_local_date(datetime(2026, 10, 7), IST)


# --- daylight saving ------------------------------------------------------------------------------------------------


def test_it_keeps_the_local_time_across_a_forward_change():
    before = next_nudge_at(utc(2026, 3, 7, 12, 0), NY, time(10, 0))
    after = next_nudge_at(utc(2026, 3, 8, 20, 0), NY, time(10, 0))
    assert before == utc(2026, 3, 7, 15, 0)  # EST, UTC-5
    assert after == utc(2026, 3, 9, 14, 0)  # EDT, UTC-4


def test_it_keeps_the_local_time_across_a_back_change():
    saturday = next_nudge_at(utc(2026, 10, 31, 15, 0), NY, time(10, 0))  # Saturday 11:00 EDT
    sunday = next_nudge_at(utc(2026, 11, 1, 16, 0), NY, time(10, 0))  # Sunday 11:00 EST
    assert saturday == utc(2026, 11, 1, 15, 0)  # Sunday 10:00 is already EST (UTC-5): the clocks went back at 02:00
    assert sunday == utc(2026, 11, 2, 15, 0)


def test_a_time_inside_the_forward_gap_is_sent_at_the_first_moment_after_it():
    # 02:30 does not exist in New York on 8 March 2026: the clocks jump from 02:00 EST to 03:00 EDT.
    due = next_nudge_at(utc(2026, 3, 8, 3, 0), NY, time(2, 30))
    assert due == utc(2026, 3, 8, 7, 30)  # 03:30 EDT, the first valid reading at or after the gap
    assert next_nudge_at(due, NY, time(2, 30)) == utc(2026, 3, 9, 6, 30)  # the next day is the normal 02:30 EDT


def test_a_time_that_happens_twice_is_sent_once_at_its_first_occurrence():
    # 01:30 happens twice in New York on 1 November 2026 (EDT then EST).
    first = next_nudge_at(utc(2026, 11, 1, 3, 0), NY, time(1, 30))
    assert first == utc(2026, 11, 1, 5, 30)  # 01:30 EDT
    # Right after it fired, the repeated 01:30 EST (06:30 UTC) must not be picked: the next is the following day.
    assert next_nudge_at(first, NY, time(1, 30)) == utc(2026, 11, 2, 6, 30)
    assert next_nudge_at(utc(2026, 11, 1, 6, 0), NY, time(1, 30)) == utc(2026, 11, 2, 6, 30)


def test_london_and_sydney_follow_their_own_rules():
    # British Summer Time ended at 01:00 UTC on 25 October, so that morning's 10:00 is already GMT (UTC+0).
    assert next_nudge_at(utc(2026, 10, 24, 12, 0), LONDON, time(10, 0)) == utc(2026, 10, 25, 10, 0)
    assert next_nudge_at(utc(2026, 10, 25, 12, 0), LONDON, time(10, 0)) == utc(2026, 10, 26, 10, 0)
    # Sydney went forward on 4 October: AEST (+10) before, AEDT (+11) after.
    assert next_nudge_at(utc(2026, 10, 2, 12, 0), SYDNEY, time(10, 0)) == utc(2026, 10, 3, 0, 0)
    assert next_nudge_at(utc(2026, 10, 5, 12, 0), SYDNEY, time(10, 0)) == utc(2026, 10, 5, 23, 0)


def test_a_zone_without_daylight_saving_never_moves():
    for day in range(1, 29):
        due = next_nudge_at(utc(2026, 10, day, 12, 0), IST, time(10, 0))
        assert due.time() == time(4, 30)


# --- moving it when the settings change ----------------------------------------------------------------------------


NOW = utc(2026, 10, 7, 6, 0)  # 11:30 in India


def test_a_nudge_is_planned_only_when_it_is_wanted():
    kw = dict(now=NOW, tz_name=IST, nudge_time=time(10, 0))
    assert schedule_nudge(enabled=True, master_on=True, **kw) == utc(2026, 10, 8, 4, 30)
    assert schedule_nudge(enabled=False, master_on=True, **kw) is None
    assert schedule_nudge(enabled=True, master_on=False, **kw) is None


def test_changing_the_zone_moves_the_instant_to_the_same_local_time_there():
    india = schedule_nudge(now=NOW, enabled=True, master_on=True, tz_name=IST, nudge_time=time(10, 0))
    london = schedule_nudge(now=NOW, enabled=True, master_on=True, tz_name=LONDON, nudge_time=time(10, 0))
    assert india == utc(2026, 10, 8, 4, 30)  # 10:00 IST tomorrow: today's 10:00 has passed
    assert london == utc(2026, 10, 7, 9, 0)  # 10:00 BST today is still ahead (it is 07:00 there) and is 09:00 UTC


def test_changing_the_time_moves_it_to_today_when_the_new_time_is_still_ahead():
    later = schedule_nudge(now=NOW, enabled=True, master_on=True, tz_name=IST, nudge_time=time(18, 0))
    assert later == utc(2026, 10, 7, 12, 30)


# --- which day a nudge belongs to ----------------------------------------------------------------------------------


def test_a_nudge_belongs_to_the_local_day_of_its_due_time():
    assert nudge_local_date(utc(2026, 10, 7, 4, 30), IST) == date(2026, 10, 7)
    assert nudge_local_date(utc(2026, 10, 7, 18, 45), IST) == date(2026, 10, 8)  # 00:15 the next morning in India
    assert nudge_local_date(utc(2026, 10, 7, 3, 59), NY) == date(2026, 10, 6)


# --- lateness -------------------------------------------------------------------------------------------------------


def test_a_nudge_stays_useful_as_long_as_the_catalogue_says():
    assert max_lateness() == get_event("daily_nudge").expires_after == timedelta(hours=6)


def test_a_slightly_late_nudge_goes_out_and_a_day_old_one_is_dropped():
    due = utc(2026, 10, 7, 4, 30)
    assert judge_nudge(now=due, due_at=due) is NudgeVerdict.SEND
    assert judge_nudge(now=due + timedelta(hours=6), due_at=due) is NudgeVerdict.SEND  # exactly at the limit
    assert judge_nudge(now=due + timedelta(hours=6, seconds=1), due_at=due) is NudgeVerdict.STALE
    assert judge_nudge(now=due + timedelta(days=2), due_at=due) is NudgeVerdict.STALE
