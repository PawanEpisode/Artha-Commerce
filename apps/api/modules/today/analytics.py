"""
Analytics events of Today (PRD section 10). The property names of every event live in `domain/event_schema.json`; the web has a
byte-identical twin (`apps/web/src/modules/today/lib/event-schema.json`) and a test fails when they drift (audit AUD-011).

`track` keeps only the properties the schema names and drops the rest (a task title can never leave through here), logging what it
dropped. The domain events Today emits through `core.events` are turned into analytics events by `install()`; the sink is a
replaceable function (default: a structured log line) so a PostHog server client can be plugged in without touching Today.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any

from core import events

logger = logging.getLogger(__name__)

SCHEMA_PATH = Path(__file__).parent / "domain" / "event_schema.json"
SCHEMA: dict = json.loads(SCHEMA_PATH.read_text())
EVENTS: dict[str, dict] = SCHEMA["events"]
NEVER_SENT: frozenset[str] = frozenset(SCHEMA["never_sent"])

Sink = Callable[[str, str, dict], None]


def _log_sink(name: str, user_id: str, props: dict) -> None:
    logger.info("analytics %s %s", name, json.dumps(props, sort_keys=True), extra={"user_id": user_id})


_sink: Sink = _log_sink


def set_sink(sink: Sink | None) -> None:
    global _sink
    _sink = sink or _log_sink


def minutes_bucket(minutes: int) -> str:
    for upper, label in ((5, "0-5"), (15, "6-15"), (30, "16-30"), (60, "31-60")):
        if minutes <= upper:
            return label
    return "61+"


def time_bucket(ms: float) -> str:
    for upper, label in ((1000, "lt1s"), (3000, "1-3s"), (10000, "3-10s"), (30000, "10-30s")):
        if ms < upper:
            return label
    return "30s+"


def conform(name: str, props: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """(the properties the schema allows, the names that were dropped). An unknown event keeps nothing."""
    spec = EVENTS.get(name)
    if spec is None:
        return {}, sorted(props)
    allowed = set(spec["props"])
    return {k: v for k, v in props.items() if k in allowed}, sorted(k for k in props if k not in allowed)


def track(name: str, user_id, **props: Any) -> dict[str, Any] | None:
    """Sends one event. Returns what was sent, or None for an event the schema does not know."""
    if name not in EVENTS:
        logger.warning("today analytics: unknown event %s", name)
        return None
    clean, dropped = conform(name, props)
    if dropped:
        logger.warning("today analytics: %s dropped %s", name, dropped)
    try:
        _sink(name, str(user_id), clean)
    except Exception:  # noqa: BLE001 - analytics never breaks the write that triggered it
        logger.exception("today analytics sink failed for %s", name)
    return clean


# ---- domain events -> analytics -------------------------------------------------------------------------------------------


def _forward(name: str):
    def handler(**payload: Any) -> None:
        props = dict(payload)
        if name == "today_task_completed":
            props["est_minutes_bucket"] = minutes_bucket(int(props.pop("est_minutes", 0) or 0))
        if name == "today_day_completed":
            props["minutes_bucket"] = minutes_bucket(int(props.pop("minutes", 0) or 0))
        track(name, payload.get("user_id", ""), **{k: v for k, v in props.items() if k in EVENTS[name]["props"]})

    handler.__name__ = f"analytics_{name}"
    return handler


SERVER_EVENTS = tuple(name for name, spec in EVENTS.items() if spec["where"] == "api")
_handlers = {name: _forward(name) for name in SERVER_EVENTS}


def install() -> None:
    for name, handler in _handlers.items():
        events.subscribe(name, handler)
