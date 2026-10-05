from datetime import UTC, datetime, timedelta

import pytest

from modules.tracking.domain import durations as d

T0 = datetime(2026, 10, 5, 4, 30, tzinfo=UTC)  # 10:00 IST


def at(**kw):
    return T0 + timedelta(**kw)


def test_elapsed_excludes_finished_pauses_and_stops_counting_at_a_pause():
    assert d.elapsed_seconds(T0, at(minutes=60), None, 600) == 3000  # 10 minute pause in a 60 minute run
    assert d.elapsed_seconds(T0, at(minutes=60), at(minutes=30), 0) == 1800  # paused at 30 minutes: stays 30
    assert d.elapsed_seconds(T0, at(minutes=1), None, 9999) == 0  # never negative


def test_client_times_are_clamped_into_the_past_twelve_hours():
    now = at(hours=20)
    assert d.clamp_client_time(None, now) == now
    assert d.clamp_client_time(at(hours=30), now) == now  # future becomes now
    assert d.clamp_client_time(at(hours=19), now) == at(hours=19)
    assert d.clamp_client_time(T0, now) == now - timedelta(hours=12)  # too old


def test_idle_rules():
    assert d.idle_due(at(minutes=10), T0, 10)
    assert not d.idle_due(at(minutes=9), T0, 10)
    assert not d.idle_due(at(hours=5), T0, 0)  # 0 = prompt off
    assert not d.idle_expired(at(minutes=1), None)
    assert d.idle_expired(at(seconds=120), T0)
    assert not d.idle_expired(at(seconds=119), T0)


def test_stop_outcome_counts_to_now_or_the_pause():
    out = d.stop_outcome(T0, at(minutes=50), paused_at=None, paused_total=300, last_active_at=at(minutes=50))
    assert (out.focus_seconds, out.idle_trimmed) == (2700, False)
    paused = d.stop_outcome(T0, at(hours=3), paused_at=at(minutes=20), paused_total=0, last_active_at=at(minutes=20))
    assert paused.focus_seconds == 1200 and paused.ended_at == at(minutes=20)


def test_a_forgotten_stopwatch_is_trimmed_to_the_last_active_moment():
    out = d.stop_outcome(T0, at(hours=30), paused_at=None, paused_total=0, last_active_at=at(hours=2))
    assert out.idle_trimmed and out.focus_seconds == 7200 and out.ended_at == at(hours=2)


def test_even_the_last_active_moment_cannot_exceed_twelve_hours():
    out = d.stop_outcome(T0, at(hours=40), paused_at=None, paused_total=0, last_active_at=at(hours=30))
    assert out.idle_trimmed and out.focus_seconds == d.MAX_SESSION_SECONDS


def test_requested_end_trims_but_never_goes_past_now():
    out = d.stop_outcome(
        T0, at(minutes=60), paused_at=None, paused_total=0, last_active_at=at(minutes=60), requested_end=at(minutes=45)
    )
    assert out.focus_seconds == 2700
    late = d.stop_outcome(
        T0, at(minutes=60), paused_at=None, paused_total=0, last_active_at=at(minutes=60), requested_end=at(hours=9)
    )
    assert late.focus_seconds == 3600


@pytest.mark.parametrize(
    ("start", "end", "code"),
    [
        (at(days=1), at(days=1, hours=1), "future"),
        (at(hours=-1), at(hours=-1), "end_before_start"),
        (at(hours=-1), at(hours=-1, seconds=30), "too_short"),
        (at(days=-3), at(days=-1, hours=1), "too_long"),
        (at(days=-400), at(days=-400, hours=1), "too_old"),
    ],
)
def test_manual_window_rules(start, end, code):
    with pytest.raises(d.DurationError) as e:
        d.validate_manual_window(start, end, T0)
    assert e.value.code == code


def test_manual_window_asks_for_confirmation_after_sixty_days_and_allows_a_small_clock_skew():
    assert d.validate_manual_window(at(days=-61), at(days=-61, hours=1), T0) is True
    assert d.validate_manual_window(at(days=-59), at(days=-59, hours=1), T0) is False
    assert d.validate_manual_window(at(hours=-1), at(minutes=4), T0) is False  # ends 4 minutes ahead: clock skew


def test_free_segments_subtract_busy_time():
    window = (at(hours=0), at(hours=4))
    busy = [(at(hours=1), at(hours=2)), (at(hours=3), at(hours=5))]
    assert d.free_segments(window, busy) == [(at(hours=0), at(hours=1)), (at(hours=2), at(hours=3))]
    assert d.free_segments(window, []) == [window]
    assert d.free_segments(window, [(at(hours=-1), at(hours=9))]) == []
    assert d.longest_segment([(at(hours=0), at(hours=1)), (at(hours=2), at(hours=2, minutes=30))]) == (
        at(hours=0),
        at(hours=1),
    )
    assert d.longest_segment([(at(hours=0), at(seconds=30))]) is None


def test_local_date_uses_the_students_zone():
    late = datetime(2026, 10, 4, 18, 0, tzinfo=UTC)  # 23:30 IST on the 4th, already the 5th in UTC+8
    assert str(d.local_date(late, "Asia/Kolkata")) == "2026-10-04"
    assert str(d.local_date(late, "Asia/Singapore")) == "2026-10-05"


def test_hour_split_inside_one_hour():
    cells = d.split_by_local_hour(T0, T0 + timedelta(minutes=30), "Asia/Kolkata")
    assert [(str(a), h, s) for a, h, s in cells] == [("2026-10-05", 10, 1800)]


def test_hour_split_across_hours_in_half_hour_offset_zone():
    cells = d.split_by_local_hour(T0 + timedelta(minutes=45), T0 + timedelta(minutes=135), "Asia/Kolkata")
    assert [(h, s) for _, h, s in cells] == [(10, 900), (11, 3600), (12, 900)]


def test_hour_split_across_midnight_lands_in_both_days():
    start = datetime(2026, 10, 4, 18, 0, tzinfo=UTC)  # 23:30 IST
    cells = d.split_by_local_hour(start, start + timedelta(hours=2), "Asia/Kolkata")
    assert [(str(a), h, s) for a, h, s in cells] == [
        ("2026-10-04", 23, 1800),
        ("2026-10-05", 0, 3600),
        ("2026-10-05", 1, 1800),
    ]
    assert d.day_seconds(cells) == {cells[0][0]: 1800, cells[1][0]: 5400}


def test_hour_split_with_pauses_adds_up_exactly_to_counted_time():
    start = datetime(2026, 10, 4, 18, 7, 13, tzinfo=UTC)
    for paused in (0, 1, 333, 1777, 5000):
        cells = d.split_by_local_hour(start, start + timedelta(hours=3, minutes=11), "Asia/Kolkata", paused)
        assert sum(s for _, _, s in cells) == 3 * 3600 + 11 * 60 - paused


def test_hour_split_in_a_zone_with_dst():
    start = datetime(2026, 7, 1, 3, 30, tzinfo=UTC)  # 23:30 in New York (UTC-4 in July)
    cells = d.split_by_local_hour(start, start + timedelta(hours=1), "America/New_York")
    assert [(str(a), h, s) for a, h, s in cells] == [("2026-06-30", 23, 1800), ("2026-07-01", 0, 1800)]


def piece(start_min, end_min, focus=None, paused=0, pauses=0):
    return d.Piece(
        at(minutes=start_min),
        at(minutes=end_min),
        focus if focus is not None else (end_min - start_min) * 60 - paused,
        paused,
        pauses,
    )


def test_merge_sums_counted_time_and_treats_the_gap_as_paused():
    merged = d.merge_pieces([piece(60, 90), piece(0, 30)])  # order does not matter
    assert (merged.started_at, merged.ended_at) == (at(minutes=0), at(minutes=90))
    assert merged.focus_seconds == 3600 and merged.paused_total_seconds == 1800


def test_merge_rejects_far_apart_or_single_sessions_and_caps_overlap_at_the_span():
    with pytest.raises(d.DurationError) as e:
        d.merge_pieces([piece(0, 30), piece(61, 90)])
    assert e.value.code == "too_far_apart"
    with pytest.raises(d.DurationError):
        d.merge_pieces([piece(0, 30)])
    overlapped = d.merge_pieces([piece(0, 60), piece(30, 90)])
    assert overlapped.focus_seconds == 5400  # sum would be 7200, but the span is 90 minutes


def test_split_gives_two_parts_and_attributes_pauses_to_the_first():
    first, second = d.split_piece(piece(0, 90, paused=600, pauses=1), at(minutes=40))
    assert (first.focus_seconds, first.paused_total_seconds, first.pause_count) == (1800, 600, 1)
    assert (second.focus_seconds, second.paused_total_seconds) == (3000, 0)
    assert first.focus_seconds + second.focus_seconds == 90 * 60 - 600


@pytest.mark.parametrize("minute", [0, 90, 200, -5])
def test_split_must_be_inside_the_session(minute):
    with pytest.raises(d.DurationError) as e:
        d.split_piece(piece(0, 90), at(minutes=minute))
    assert e.value.code == "outside"


def test_split_parts_need_a_minute_each():
    with pytest.raises(d.DurationError) as e:
        d.split_piece(piece(0, 90), at(minutes=89, seconds=30))
    assert e.value.code == "too_short"
    with pytest.raises(d.DurationError):
        d.split_piece(piece(0, 90, paused=1700), at(minutes=20))  # the pauses leave no minute in the first part
