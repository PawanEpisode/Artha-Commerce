from datetime import UTC, datetime, timedelta

import pytest

from modules.focus.domain import timing

T0 = datetime(2026, 10, 5, 4, 30, tzinfo=UTC)


def test_presets_match_the_prd():
    assert timing.PRESETS["classic"] == {
        "focus_minutes": 25,
        "short_break_minutes": 5,
        "long_break_minutes": 15,
        "rounds_before_long": 4,
    }
    assert timing.PRESETS["deep"]["focus_minutes"] == 50 and timing.PRESETS["deep"]["rounds_before_long"] == 3
    assert timing.PRESETS["light"]["short_break_minutes"] == 3


@pytest.mark.parametrize(
    "custom",
    [
        {"focus_minutes": 4, "short_break_minutes": 5, "long_break_minutes": 15, "rounds_before_long": 4},
        {"focus_minutes": 121, "short_break_minutes": 5, "long_break_minutes": 15, "rounds_before_long": 4},
        {"focus_minutes": 25, "short_break_minutes": 0, "long_break_minutes": 15, "rounds_before_long": 4},
        {"focus_minutes": 25, "short_break_minutes": 5, "long_break_minutes": 61, "rounds_before_long": 4},
        {"focus_minutes": 25, "short_break_minutes": 5, "long_break_minutes": 15, "rounds_before_long": 9},
        {"focus_minutes": 25, "short_break_minutes": 5, "long_break_minutes": 15, "rounds_before_long": 1},
    ],
)
def test_custom_timings_outside_the_limits_are_refused(custom):
    with pytest.raises(timing.TimingError) as exc:
        timing.resolve_preset("custom", custom)
    assert exc.value.code == "out_of_range"


def test_custom_needs_every_duration_and_unknown_presets_fail():
    with pytest.raises(timing.TimingError):
        timing.resolve_preset("custom", {"focus_minutes": 30})
    with pytest.raises(timing.TimingError):
        timing.resolve_preset("marathon")


def test_boundary_values_are_allowed():
    ok = {"focus_minutes": 5, "short_break_minutes": 1, "long_break_minutes": 60, "rounds_before_long": 8}
    assert timing.resolve_preset("custom", ok) == ok


def test_pause_maths_and_refresh_at_ten_minutes_three_seconds():
    now = T0 + timedelta(minutes=10, seconds=3)
    assert timing.remaining(1500, T0, now, None, 0) == 897  # 14:57
    paused = T0 + timedelta(minutes=10)
    assert timing.remaining(1500, T0, now, paused, 0) == 900  # frozen while paused
    assert timing.remaining(1500, T0, now, None, 300) == 1197  # a finished 5 minute pause is not counted


def test_a_phase_ends_after_the_planned_time_plus_pauses():
    assert timing.phase_end_at(T0, 1500, 300) == T0 + timedelta(seconds=1800)
    assert not timing.finished(1500, T0, T0 + timedelta(seconds=1799), None, 300)
    assert timing.finished(1500, T0, T0 + timedelta(seconds=1800), None, 300)
    assert not timing.finished(1500, T0, T0 + timedelta(hours=9), T0 + timedelta(minutes=5), 0)  # paused never ends


def test_presence_window_is_two_minutes_before_the_end():
    end = T0 + timedelta(minutes=25)
    assert timing.was_present(end - timedelta(seconds=120), end)
    assert not timing.was_present(end - timedelta(seconds=121), end)


def test_the_long_break_comes_after_the_last_round():
    assert [timing.break_after(r, 4) for r in (1, 2, 3, 4)] == ["short_break"] * 3 + ["long_break"]
    assert timing.break_after(3, 3) == "long_break"


def test_cycle_memory_fades_after_four_hours():
    assert timing.cycle_fresh(T0, T0 + timedelta(hours=4))
    assert not timing.cycle_fresh(T0, T0 + timedelta(hours=4, seconds=1))
    assert not timing.cycle_fresh(None, T0)
