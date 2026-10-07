"""
Buttons on a timer alert (X-01.1 FR-N12, W3.6). Pure: which buttons an alert carries, what they say, how long a button
works, how its one-time token is stored, and what the confirmation says after a tap. What a button does to the timer is
decided by `focus` (`focus.services.act_from_notification`), the owner of the timer.

Buttons are an Android (Chromium) feature of Web Push, so only devices registered with platform `android` get them.
The token is 32 random bytes in base64url (43 characters). Only its SHA-256 is stored, so a database leak cannot be
replayed, and a lookup by hash reveals nothing about the token through timing.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from .enums import ButtonAction, DevicePlatform

#: How long a button works after the alert (ERD 2.8). The timer's version check makes a later change a no-op anyway.
TOKEN_TTL = timedelta(minutes=10)
TOKEN_BYTES = 32
_TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9_-]{43}$")
#: Put this name in `NOTIFICATIONS_DISABLED_EVENTS` to stop offering buttons and refuse every tap (the alerts still go).
KILL_SWITCH = "timer_buttons"
PLATFORMS: frozenset[str] = frozenset({DevicePlatform.ANDROID.value})


def buttons_for(event_key: str, context: Mapping[str, Any]) -> tuple[ButtonAction, ...]:
    """
    The buttons for one alert, in the order shown (Android shows at most two). None when the round waits for the
    student's own answer in the app (`away`), and none for a round whose break begins by itself.
    """
    if context.get("away"):
        return ()
    if event_key == "timer_end":
        if context.get("overtime"):  # the round runs on past its target until the student stops it
            return (ButtonAction.START_BREAK, ButtonAction.PAUSE)
        return () if context.get("break_starts_itself") else (ButtonAction.START_BREAK,)
    if event_key == "break_over":
        return (ButtonAction.START_FOCUS,)
    return ()


def button_title(action: ButtonAction, context: Mapping[str, Any] | None = None) -> str:
    if action is ButtonAction.START_FOCUS:
        next_round = (context or {}).get("next_round")
        return f"Start round {int(next_round)}" if next_round else "Start next round"
    return {
        ButtonAction.PAUSE: "Pause",
        ButtonAction.RESUME: "Resume",
        ButtonAction.START_BREAK: "Start break",
    }[action]


def well_formed(token: object) -> bool:
    return isinstance(token, str) and bool(_TOKEN_PATTERN.match(token))


def hash_token(token: str) -> str:
    """The stored form of a token: SHA-256, 64 hex characters."""
    return hashlib.sha256(token.encode("ascii")).hexdigest()


@dataclass(frozen=True)
class Confirmation:
    title: str
    body: str


_DONE = {
    ButtonAction.PAUSE: Confirmation("Timer paused", "Your round is on hold. Resume when you are back."),
    ButtonAction.RESUME: Confirmation("Timer running", "Your round is counting again."),
    ButtonAction.START_BREAK: Confirmation("Break started", "Round saved. Enjoy your break."),
    ButtonAction.START_FOCUS: Confirmation("Round started", "Your next round is running."),
}
_ALREADY = {
    ButtonAction.PAUSE: Confirmation("Already paused", "Your round is on hold."),
    ButtonAction.RESUME: Confirmation("Already running", "Your round is counting."),
    ButtonAction.START_BREAK: Confirmation("Break running", "Your break has already started."),
    ButtonAction.START_FOCUS: Confirmation("Round running", "Your next round has already started."),
}
STALE = Confirmation("Nothing changed", "The timer changed after this alert. Open the app to see where it is.")
NEEDS_APP = Confirmation("Open the app", "Tell us whether you studied through this round to save it.")


def confirmation(action: ButtonAction, outcome: str) -> Confirmation:
    """What the notification says after a tap. `outcome` is `done`, `already`, `stale` or `needs_app`."""
    if outcome == "done":
        return _DONE[action]
    if outcome == "already":
        return _ALREADY[action]
    if outcome == "needs_app":
        return NEEDS_APP
    return STALE
