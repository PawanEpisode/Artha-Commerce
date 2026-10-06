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


def _test_push(context: Mapping[str, Any]) -> Copy:
    return Copy("Test notification", "Notifications are working on this device.", SETTINGS_LINK, "test_push")


_BUILDERS: Mapping[str, Callable[[Mapping[str, Any]], Copy]] = {
    "timer_end": _timer_end,
    "break_over": _break_over,
    "test_push": _test_push,
}


def build_copy(event_key: str, context: Mapping[str, Any]) -> Copy:
    """The words for an event. Events without a builder yet raise `UnknownEvent`, so they cannot be sent unreviewed."""
    try:
        builder = _BUILDERS[event_key]
    except KeyError:
        raise UnknownEvent(event_key) from None
    return builder(context)
