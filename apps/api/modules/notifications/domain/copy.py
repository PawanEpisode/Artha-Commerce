"""
What each notification says. Pure builders keyed by event, so wording lives in one file, is unit tested and can be
translated later without touching delivery code. Voice: warm, specific, never shaming, no emoji. Titles stay under
about 40 characters and bodies under about 100 so lock screens do not cut them.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from .catalogue import UnknownEvent

TITLE_LIMIT = 40
BODY_LIMIT = 100
FOCUS_LINK = "/app/focus"
TRACKER_LINK = "/app/tracker"
SETTINGS_LINK = "/app/settings/notifications"


@dataclass(frozen=True)
class Copy:
    title: str
    body: str
    deep_link: str
    tag: str


def _fit(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def _plural(count: int, word: str) -> str:
    return f"{count} {word}" if count == 1 else f"{count} {word}s"


def _timer_end(context: Mapping[str, Any]) -> Copy:
    """A focus round ended, or reached its target while overtime keeps it running (the default setting)."""
    minutes = int(context["minutes"])
    subject = context.get("subject_name")
    spent = f"{_plural(minutes, 'minute')} on {subject}" if subject else _plural(minutes, "minute")
    if context.get("overtime"):
        title = "Round target reached"
        body = f"{spent}. The timer is still running; stop when you are ready."
    else:
        title = f"Round {int(context['round_number'])} done"
        break_minutes = context.get("break_minutes")
        advice = f"Take {break_minutes}, you earned it." if break_minutes else "Take a break, you earned it."
        body = f"{spent}. {advice}"
    return Copy(_fit(title, TITLE_LIMIT), _fit(body, BODY_LIMIT), FOCUS_LINK, f"timer:{context['client_id']}")


def _break_over(context: Mapping[str, Any]) -> Copy:
    next_round = context.get("next_round")
    body = f"Ready for round {int(next_round)}?" if next_round else "Ready for your next round?"
    return Copy("Break over", body, FOCUS_LINK, f"timer:{context['client_id']}")


def duration_label(minutes: int) -> str:
    """Whole minutes as a short phrase: 45 min, 1 h, 3 h 12 min."""
    minutes = max(0, int(minutes))
    hours, rest = divmod(minutes, 60)
    if not hours:
        return f"{rest} min"
    return f"{hours} h" if not rest else f"{hours} h {rest} min"


def _stopwatch_long(context: Mapping[str, Any]) -> Copy:
    """The stopwatch has counted three hours and is still running: a nudge to check it is not forgotten."""
    body = f"{duration_label(int(context['minutes']))} so far. Pause or stop it if you are done."
    return Copy("Stopwatch still running", _fit(body, BODY_LIMIT), TRACKER_LINK, f"stopwatch:{context['client_id']}")


def _goal_reached(context: Mapping[str, Any]) -> Copy:
    body = f"{duration_label(int(context['studied_minutes']))} studied today."
    return Copy("Daily goal reached", _fit(body, BODY_LIMIT), TRACKER_LINK, f"goal:{context['local_date']}")


def _streak_at_risk(context: Mapping[str, Any]) -> Copy:
    """Today's goal is not met and the streak ends at yesterday: say how much is left, never shame."""
    days = int(context["streak_days"])
    title = f"Keep your {days}-day streak" if days > 1 else "Keep your streak going"
    body = f"{duration_label(int(context['remaining_minutes']))} more today meets your goal."
    return Copy(_fit(title, TITLE_LIMIT), _fit(body, BODY_LIMIT), TRACKER_LINK, f"streak:{context['local_date']}")


def _test_push(context: Mapping[str, Any]) -> Copy:
    return Copy("Test notification", "Notifications are working on this device.", SETTINGS_LINK, "test_push")


_BUILDERS: Mapping[str, Callable[[Mapping[str, Any]], Copy]] = {
    "timer_end": _timer_end,
    "break_over": _break_over,
    "stopwatch_long": _stopwatch_long,
    "goal_reached": _goal_reached,
    "streak_at_risk": _streak_at_risk,
    "test_push": _test_push,
}


def build_copy(event_key: str, context: Mapping[str, Any]) -> Copy:
    """The words for an event. Events without a builder yet raise `UnknownEvent`, so they cannot be sent unreviewed."""
    try:
        builder = _BUILDERS[event_key]
    except KeyError:
        raise UnknownEvent(event_key) from None
    return builder(context)
