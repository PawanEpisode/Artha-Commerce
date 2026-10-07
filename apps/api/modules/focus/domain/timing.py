"""
Pure Pomodoro rules (F-01.1). No Django, no database. The web mirrors the presets and limits in
`modules/focus/lib/presets.ts`; `tests/test_web_parity.py` pins both. The server is the clock: every figure derives from
timestamps and the stored pause total, never from counting ticks.
"""

from __future__ import annotations

from datetime import datetime, timedelta

# --- Presets and limits (PRD 5.1) --------------------------------------------------------------------------------
PRESETS: dict[str, dict[str, int]] = {
    "classic": {"focus_minutes": 25, "short_break_minutes": 5, "long_break_minutes": 15, "rounds_before_long": 4},
    "deep": {"focus_minutes": 50, "short_break_minutes": 10, "long_break_minutes": 20, "rounds_before_long": 3},
    "light": {"focus_minutes": 15, "short_break_minutes": 3, "long_break_minutes": 10, "rounds_before_long": 4},
}
PRESET_KEYS = (*PRESETS, "custom")
DEFAULT_PRESET = "classic"

FOCUS_MINUTES = (5, 120)
SHORT_BREAK_MINUTES = (1, 30)
LONG_BREAK_MINUTES = (5, 60)
ROUNDS_BEFORE_LONG = (2, 8)

EXTEND_SECONDS = 300
MAX_EXTENSIONS = 3
PRESENCE_WINDOW_SECONDS = 120  # a focus round counts on its own only if the tab was seen this close to its end
CYCLE_MEMORY_SECONDS = 4 * 3600  # a half-finished cycle is forgotten after four idle hours
MIN_ROUND_SECONDS = 60
PLANNED_MIN_SECONDS, PLANNED_MAX_SECONDS = 60, 14400
COMPLETE_TOLERANCE_SECONDS = 2  # the client may report the end a moment before the server's clock reaches it
HEARTBEAT_SECONDS = 20
# Overtime: a focus round that reaches its planned length keeps counting until the student stops it. It never runs
# unattended: once the tab has not been seen for the presence window the round closes at the last sighting, and the
# extra time is capped.
OVERTIME_MAX_SECONDS = 2 * 3600

PHASES = ("focus", "short_break", "long_break")
# The floating timer's two sizes (X-01 PRD B). Only the name is stored; the web owns the pixel sizes.
POPOUT_SIZES = ("pill", "card")
REASONS = ("distracted", "phone_call", "tired", "urgent_work", "other")


class TimingError(ValueError):
    def __init__(self, code: str, message: str, field: str | None = None):
        super().__init__(message)
        self.code = code
        self.field = field


def _within(name: str, value: int, bounds: tuple[int, int], label: str) -> int:
    low, high = bounds
    if not isinstance(value, int) or isinstance(value, bool) or not low <= value <= high:
        raise TimingError("out_of_range", f"{label} must be between {low} and {high}.", name)
    return value


def resolve_preset(preset: str, custom: dict | None = None) -> dict[str, int]:
    """The four durations for a preset key. `custom` is validated against the limits."""
    if preset in PRESETS:
        return dict(PRESETS[preset])
    if preset != "custom":
        raise TimingError("unknown_preset", "Unknown preset.", "preset")
    custom = custom or {}
    missing = [k for k in PRESETS["classic"] if k not in custom]
    if missing:
        raise TimingError("missing", "Custom timings need every duration.", missing[0])
    return validate_durations(custom)


def validate_durations(values: dict) -> dict[str, int]:
    return {
        "focus_minutes": _within("focus_minutes", values["focus_minutes"], FOCUS_MINUTES, "Focus length"),
        "short_break_minutes": _within(
            "short_break_minutes", values["short_break_minutes"], SHORT_BREAK_MINUTES, "Short break"
        ),
        "long_break_minutes": _within(
            "long_break_minutes", values["long_break_minutes"], LONG_BREAK_MINUTES, "Long break"
        ),
        "rounds_before_long": _within(
            "rounds_before_long", values["rounds_before_long"], ROUNDS_BEFORE_LONG, "Rounds before a long break"
        ),
    }


def planned_seconds(phase: str, d: dict) -> int:
    minutes = {
        "focus": d["focus_minutes"],
        "short_break": d["short_break_minutes"],
        "long_break": d["long_break_minutes"],
    }[phase]
    return minutes * 60


def break_after(round_number: int, rounds_before_long: int) -> str:
    return "long_break" if round_number >= rounds_before_long else "short_break"


# --- Clock maths -------------------------------------------------------------------------------------------------
def elapsed(started_at: datetime, now: datetime, paused_at: datetime | None, paused_total: int) -> int:
    end = min(now, paused_at) if paused_at else now
    return max(0, int((end - started_at).total_seconds()) - paused_total)


def remaining(planned: int, started_at, now, paused_at, paused_total) -> int:
    return max(0, planned - elapsed(started_at, now, paused_at, paused_total))


def phase_end_at(started_at: datetime, planned: int, paused_total: int) -> datetime:
    """When a phase that is not paused reaches zero."""
    return started_at + timedelta(seconds=planned + paused_total)


def finished(planned, started_at, now, paused_at, paused_total) -> bool:
    return paused_at is None and now >= phase_end_at(started_at, planned, paused_total)


def was_present(last_seen_at: datetime, end_at: datetime) -> bool:
    """FR: the student counts as there if the tab was seen within two minutes of the end (or after it)."""
    return last_seen_at >= end_at - timedelta(seconds=PRESENCE_WINDOW_SECONDS)


def present_by_tap(end_at: datetime, tap_at: datetime) -> bool:
    """
    X-01.1 FR-N12: a tap on a button of the timer alert counts as the student being there when it comes no later than
    the presence window after the end. A later tap is no evidence of the moment the round ended.
    """
    return tap_at <= end_at + timedelta(seconds=PRESENCE_WINDOW_SECONDS)


def cycle_fresh(updated_at: datetime | None, now: datetime) -> bool:
    return updated_at is not None and (now - updated_at).total_seconds() <= CYCLE_MEMORY_SECONDS


def overtime_seconds(elapsed_seconds: int, planned: int) -> int:
    """Seconds counted beyond the planned length of a focus round (0 until it is reached)."""
    return max(0, elapsed_seconds - planned)


def overtime_holds(end_at: datetime, last_seen_at: datetime, now: datetime) -> bool:
    """
    A round past its planned end keeps running while the student is still there (the tab was seen within the presence
    window) and the extra time is under the cap. Otherwise it closes at the last sighting.
    """
    return (now - last_seen_at).total_seconds() <= PRESENCE_WINDOW_SECONDS and (
        now - end_at
    ).total_seconds() < OVERTIME_MAX_SECONDS


def overtime_stop(end_at: datetime, last_seen_at: datetime) -> datetime:
    """Where an abandoned overtime round closes: the last time the student was seen, never before the planned end."""
    return min(max(end_at, last_seen_at), end_at + timedelta(seconds=OVERTIME_MAX_SECONDS))
