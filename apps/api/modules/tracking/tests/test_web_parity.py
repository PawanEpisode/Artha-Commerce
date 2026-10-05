"""The web tracker mirrors a few limits and the heat-map edges. This fails when the two sides drift apart."""

import re
from pathlib import Path

from modules.tracking.domain import durations, reports

LIMITS_TS = Path(__file__).resolve().parents[5] / "apps/web/src/modules/tracker/lib/limits.ts"


def _web_limits() -> dict[str, object]:
    text = LIMITS_TS.read_text()
    out: dict[str, object] = {}
    for name, value in re.findall(r"export const ([A-Z_]+) = (\d+)\b", text):
        out[name] = int(value)
    edges = re.search(r"HEATMAP_EDGES_SECONDS = \[([^\]]+)\]", text)
    assert edges, "HEATMAP_EDGES_SECONDS not found in limits.ts"
    out["HEATMAP_EDGES_SECONDS"] = tuple(int(x) for x in edges.group(1).split(","))
    return out


def test_web_limits_match_the_api():
    web = _web_limits()
    api = {name: getattr(durations, name) for name in web if hasattr(durations, name)}
    api["HEATMAP_EDGES_SECONDS"] = reports.HEATMAP_EDGES_SECONDS
    missing = [name for name in web if name not in api]
    assert not missing, f"limits.ts has constants the API does not define: {missing}"
    assert web == api


def test_every_numeric_api_limit_is_mirrored_on_the_web():
    web = _web_limits()
    shared = [
        "MIN_SESSION_SECONDS",
        "MAX_MANUAL_SPAN_SECONDS",
        "CONFIRM_OLDER_THAN_DAYS",
        "REJECT_OLDER_THAN_DAYS",
        "CLOCK_SKEW_SECONDS",
        "UNDO_SECONDS",
        "IDLE_ANSWER_SECONDS",
        "MERGE_MAX_GAP_SECONDS",
        "NOTE_MAX_CHARS",
        "GOAL_DAILY_MIN",
        "GOAL_DAILY_MAX",
        "GOAL_WEEKLY_MIN",
        "GOAL_WEEKLY_MAX",
    ]
    assert [name for name in shared if name not in web] == []
