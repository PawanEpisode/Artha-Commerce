"""
The task state machine in one place (PRD 5.2, ERD 3.5). Services call `transition`; the web mirrors it in `lib/transitions.ts`
and both run the shared cases in `tests/fixtures/state_transitions.json`, so the optimistic UI cannot drift from the server.

Pure: no clock (callers pass `within_undo` and `within_grace`), no database.
"""

from __future__ import annotations

from datetime import datetime

from .constants import UNDO_WINDOW_SECONDS

ACTIONS = (
    "start",
    "pin",
    "complete_manual",
    "complete_event",
    "skip",
    "swap",
    "snooze",
    "expire",
    "restore",
    "undo",
    "move",
)

#: The state an action leads to. `undo` is special (it returns to the state before the tick) and is handled separately.
TARGET = {
    "start": "accepted",
    "pin": "accepted",
    "complete_manual": "done",
    "complete_event": "done",
    "skip": "skipped",
    "swap": "skipped",
    "snooze": "snoozed",
    "expire": "expired",
    "restore": "suggested",
    "move": "suggested",
}

_FROM_OPEN = {"complete_manual", "complete_event", "skip", "swap", "snooze", "expire"}
_RULES: dict[str, set[str]] = {
    "suggested": _FROM_OPEN | {"start", "pin"},
    "accepted": set(_FROM_OPEN),
    "done": {"undo"},
    "skipped": {"restore", "expire"},
    "snoozed": {"move", "expire"},
    "expired": {"complete_event"},
}


class InvalidTransition(Exception):
    """422 `invalid_transition`: carries the actions the task allows from where it is."""

    def __init__(self, state: str, action: str, allowed: tuple[str, ...]):
        super().__init__(f"{action} is not allowed from {state}")
        self.state, self.action, self.allowed = state, action, allowed


class UndoExpired(Exception):
    """410: the 60 second undo window has passed (or there is nothing to undo to)."""


def allowed_actions(state: str, *, origin: str = "provider") -> tuple[str, ...]:
    actions = set(_RULES.get(state, ()))
    if state == "snoozed" and origin != "user":
        actions.discard("move")  # a provider task stays suppressed until its date, then its provider re-offers it
    return tuple(a for a in ACTIONS if a in actions)


def allowed_targets(state: str, *, origin: str = "provider", prev_state: str | None = None) -> tuple[str, ...]:
    """The states reachable from `state`, for the `allowed` list of a 422 body and for the UI's menu."""
    out: list[str] = []
    for action in allowed_actions(state, origin=origin):
        target = prev_state if action == "undo" else TARGET[action]
        if target and target not in out:
            out.append(target)
    return tuple(out)


def undo_window_open(state_changed_at: datetime, now: datetime) -> bool:
    return (now - state_changed_at).total_seconds() <= UNDO_WINDOW_SECONDS


def transition(
    state: str,
    action: str,
    *,
    prev_state: str | None = None,
    origin: str = "provider",
    within_undo: bool = True,
    within_grace: bool = True,
    same_day: bool = True,
) -> str:
    """
    The new state, or the same state when the action already holds (a replay is not an error, FR idempotency). Raises
    `InvalidTransition` when the move is not in the table and `UndoExpired` when an undo is too late.
    """
    if action not in ACTIONS:
        raise InvalidTransition(state, action, allowed_actions(state, origin=origin))

    if action == "undo":
        if state != "done":
            raise InvalidTransition(state, action, allowed_actions(state, origin=origin))
        if not within_undo or prev_state not in ("suggested", "accepted"):
            raise UndoExpired("The undo window has passed.")
        return prev_state

    target = TARGET[action]
    if state == target:
        return state  # idempotent: already there
    if state == "done" and action in ("complete_manual", "complete_event"):
        return state

    if action not in allowed_actions(state, origin=origin):
        raise InvalidTransition(state, action, allowed_actions(state, origin=origin))
    if state == "expired" and not within_grace:
        raise InvalidTransition(state, action, ())  # past the late-night grace an expired task is final
    if action == "restore" and not same_day:
        raise InvalidTransition(
            state, action, tuple(a for a in allowed_actions(state, origin=origin) if a != "restore")
        )
    return target


def incoming_wins(
    current_state: str,
    action: str,
    *,
    current_changed_ts: float,
    client_ts: float,
) -> bool:
    """
    Cross-device conflict rule (ERD 3.5). Completing always wins over a non-done task (done is terminal against any later
    write: a stale skip never beats done). Against a done task only an undo or a repeat of the completion is applied.
    Between non-terminal states the later `client_ts` wins; the loser gets 409 `state_conflict` with the current task.
    """
    if action in ("complete_manual", "complete_event"):
        return True
    if current_state == "done":
        return action == "undo"
    return client_ts >= current_changed_ts
