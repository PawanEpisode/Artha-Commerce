"""The web mirrors the Pomodoro presets and limits (`modules/focus/lib/presets.ts`). This test fails when they drift."""

import re
from pathlib import Path

from modules.focus.domain import timing

PRESETS_TS = Path(__file__).resolve().parents[5] / "apps/web/src/modules/focus/lib/presets.ts"


def _text() -> str:
    assert PRESETS_TS.exists(), f"missing {PRESETS_TS}"
    return PRESETS_TS.read_text()


def test_numeric_limits_match():
    web = {m.group(1): int(m.group(2)) for m in re.finditer(r"^export const ([A-Z_]+) = (\d+)$", _text(), re.M)}
    api = {
        "FOCUS_MINUTES_MIN": timing.FOCUS_MINUTES[0],
        "FOCUS_MINUTES_MAX": timing.FOCUS_MINUTES[1],
        "SHORT_BREAK_MINUTES_MIN": timing.SHORT_BREAK_MINUTES[0],
        "SHORT_BREAK_MINUTES_MAX": timing.SHORT_BREAK_MINUTES[1],
        "LONG_BREAK_MINUTES_MIN": timing.LONG_BREAK_MINUTES[0],
        "LONG_BREAK_MINUTES_MAX": timing.LONG_BREAK_MINUTES[1],
        "ROUNDS_BEFORE_LONG_MIN": timing.ROUNDS_BEFORE_LONG[0],
        "ROUNDS_BEFORE_LONG_MAX": timing.ROUNDS_BEFORE_LONG[1],
        "EXTEND_SECONDS": timing.EXTEND_SECONDS,
        "MAX_EXTENSIONS": timing.MAX_EXTENSIONS,
        "PRESENCE_WINDOW_SECONDS": timing.PRESENCE_WINDOW_SECONDS,
        "MIN_ROUND_SECONDS": timing.MIN_ROUND_SECONDS,
        "HEARTBEAT_SECONDS": timing.HEARTBEAT_SECONDS,
    }
    assert len(web) >= 13
    assert web == api


def test_presets_match():
    web = {
        m.group(1): [int(n) for n in m.group(2).split(",")]
        for m in re.finditer(r"^\s+(\w+): \[([\d, ]+)\],$", _text(), re.M)
    }
    api = {
        key: [p["focus_minutes"], p["short_break_minutes"], p["long_break_minutes"], p["rounds_before_long"]]
        for key, p in timing.PRESETS.items()
    }
    assert web == api
