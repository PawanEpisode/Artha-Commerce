"""When the tracker alerts happen and what they say (X-01.1 W3.2). Pure: no database, no clock."""

from datetime import UTC, date, datetime, time, timedelta

import pytest

from modules.notifications.domain import tracker_alerts
from modules.notifications.domain.catalogue import UnknownEvent
from modules.notifications.domain.copy import BODY_LIMIT, TITLE_LIMIT, build_copy, duration_label
from modules.notifications.domain.deeplinks import is_allowed
from modules.notifications.domain.policy import QuietPreference

IST = "Asia/Kolkata"
DAY = date(2026, 10, 5)


def utc(*args):
    return datetime(*args, tzinfo=UTC)


def quiet(start=time(22, 0), end=time(7, 0), *, enabled=True, tz=IST):
    return QuietPreference(enabled, tz, start, end)


# --- the day's end and the streak window ---------------------------------------------------------------------------


def test_without_quiet_hours_the_day_ends_at_local_midnight():
    assert tracker_alerts.day_end(DAY, IST, None) == utc(2026, 10, 5, 18, 30)
    assert tracker_alerts.day_end(DAY, IST, quiet(enabled=False)) == utc(2026, 10, 5, 18, 30)


def test_an_overnight_quiet_window_ends_the_day_when_it_starts():
    assert tracker_alerts.day_end(DAY, IST, quiet()) == utc(2026, 10, 5, 16, 30)  # 22:00 in India
    assert tracker_alerts.day_end(DAY, IST, quiet(time(23, 30), time(6, 0))) == utc(2026, 10, 5, 18, 0)


def test_quiet_hours_that_start_after_the_day_has_ended_or_in_daytime_change_nothing():
    assert tracker_alerts.day_end(DAY, IST, quiet(time(13, 0), time(15, 0))) == utc(2026, 10, 5, 18, 30)
    assert tracker_alerts.day_end(DAY, IST, quiet(time(0, 30), time(7, 0))) == utc(2026, 10, 5, 18, 30)


def test_the_quiet_clock_can_be_in_another_time_zone_than_the_tracker_day():
    # Quiet from 22:00 in London (21:00 UTC in October) while the tracker day is India's: 21:00 UTC is after India's
    # midnight (18:30 UTC), so midnight still ends the day.
    assert tracker_alerts.day_end(DAY, IST, quiet(tz="Europe/London")) == utc(2026, 10, 5, 18, 30)
    # Quiet from 22:00 in Dubai (18:00 UTC) starts before India's midnight, so it ends the day.
    assert tracker_alerts.day_end(DAY, IST, quiet(tz="Asia/Dubai")) == utc(2026, 10, 5, 18, 0)


def test_the_window_opens_ninety_minutes_before_the_day_ends():
    start, end = tracker_alerts.streak_window(DAY, IST, quiet(enabled=False))
    assert (start, end) == (utc(2026, 10, 5, 17, 0), utc(2026, 10, 5, 18, 30))  # 22:30 to 24:00 in India
    start, end = tracker_alerts.streak_window(DAY, IST, quiet())
    assert (start, end) == (utc(2026, 10, 5, 15, 0), utc(2026, 10, 5, 16, 30))  # 20:30 to 22:00: before quiet hours


def test_the_window_never_opens_before_the_earliest_local_time():
    start, end = tracker_alerts.streak_window(DAY, IST, quiet(time(17, 30), time(6, 0)))
    assert start == utc(2026, 10, 5, 10, 30) and end == utc(2026, 10, 5, 12, 0)  # opens 16:00, closes 17:30 local


def test_a_day_that_ends_before_the_earliest_time_has_no_window():
    assert tracker_alerts.streak_window(DAY, IST, quiet(time(15, 0), time(6, 0))) is None


def test_the_window_follows_daylight_saving_in_the_students_zone():
    start, end = tracker_alerts.streak_window(
        date(2026, 3, 8), "America/New_York", None
    )  # clocks went forward that day
    assert end - start == timedelta(minutes=90)
    assert end == utc(2026, 3, 9, 4, 0)  # midnight at UTC-4


def test_the_stopwatch_mark_is_three_hours():
    assert tracker_alerts.stopwatch_long_after_seconds() == 3 * 3600


# --- the words -----------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "minutes, label", [(0, "0 min"), (1, "1 min"), (45, "45 min"), (60, "1 h"), (192, "3 h 12 min"), (600, "10 h")]
)
def test_durations_read_like_a_person_would_say_them(minutes, label):
    assert duration_label(minutes) == label


def test_the_stopwatch_alert_names_the_time_and_links_to_the_tracker():
    copy = build_copy("stopwatch_long", {"client_id": "abc", "minutes": 181})
    assert (copy.title, copy.deep_link, copy.tag) == ("Stopwatch still running", "/app/tracker", "stopwatch:abc")
    assert copy.body == "3 h 1 min so far. Pause or stop it if you are done."


def test_the_goal_alert_says_what_was_studied_today():
    copy = build_copy("goal_reached", {"local_date": "2026-10-05", "studied_minutes": 192, "goal_minutes": 180})
    assert (copy.title, copy.body) == ("Daily goal reached", "3 h 12 min studied today.")
    assert (copy.deep_link, copy.tag) == ("/app/tracker", "goal:2026-10-05")


def test_the_streak_alert_says_how_much_is_left_and_never_shames():
    copy = build_copy("streak_at_risk", {"local_date": "2026-10-05", "streak_days": 12, "remaining_minutes": 80})
    assert copy.title == "Keep your 12-day streak"
    assert copy.body == "1 h 20 min more today meets your goal."
    assert (copy.deep_link, copy.tag) == ("/app/tracker", "streak:2026-10-05")


def test_a_streak_of_one_day_does_not_say_one_day_streak():
    copy = build_copy("streak_at_risk", {"local_date": "2026-10-05", "streak_days": 1, "remaining_minutes": 30})
    assert copy.title == "Keep your streak going"


@pytest.mark.parametrize(
    "event, context",
    [
        ("stopwatch_long", {"client_id": "abc", "minutes": 720}),
        ("goal_reached", {"local_date": "2026-10-05", "studied_minutes": 1440, "goal_minutes": 1440}),
        ("streak_at_risk", {"local_date": "2026-10-05", "streak_days": 400, "remaining_minutes": 1439}),
    ],
)
def test_every_tracker_alert_fits_a_lock_screen_and_links_inside_the_allow_list(event, context):
    copy = build_copy(event, context)
    assert len(copy.title) <= TITLE_LIMIT and len(copy.body) <= BODY_LIMIT
    assert is_allowed(copy.deep_link) and not any(ord(c) > 0x2000 and c != "…" for c in copy.title + copy.body)


def test_events_still_without_a_builder_stay_unsendable():
    with pytest.raises(UnknownEvent):
        build_copy("daily_nudge", {})
