"""The task state machine. The cases live in a JSON file that the web mirror runs too (`lib/transitions.ts`)."""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from modules.today.domain import states
from modules.today.domain.constants import TASK_STATES

CASES = json.loads((Path(__file__).parent / "fixtures" / "state_transitions.json").read_text())


@pytest.mark.parametrize("case", CASES["transitions"], ids=lambda c: c["name"])
def test_shared_transition_cases(case):
    kwargs = {k: case[k] for k in ("prev_state", "origin", "within_undo", "within_grace", "same_day") if k in case}
    if "to" in case:
        assert states.transition(case["state"], case["action"], **kwargs) == case["to"]
        return
    if case["error"] == "undo_expired":
        with pytest.raises(states.UndoExpired):
            states.transition(case["state"], case["action"], **kwargs)
        return
    with pytest.raises(states.InvalidTransition) as err:
        states.transition(case["state"], case["action"], **kwargs)
    assert sorted(err.value.allowed) == sorted(case["allowed"])


@pytest.mark.parametrize("case", CASES["conflicts"], ids=lambda c: c["name"])
def test_shared_conflict_cases(case):
    assert (
        states.incoming_wins(
            case["state"], case["action"], current_changed_ts=case["current_ts"], client_ts=case["client_ts"]
        )
        is case["wins"]
    )


def test_every_state_in_the_table_is_a_database_state():
    assert set(states._RULES) == set(TASK_STATES)
    assert set(states.TARGET.values()) <= set(TASK_STATES)


def test_allowed_targets_for_the_error_body_and_the_menu():
    assert states.allowed_targets("suggested") == ("accepted", "done", "skipped", "snoozed", "expired")
    assert states.allowed_targets("done", prev_state="accepted") == ("accepted",)
    assert states.allowed_targets("snoozed", origin="provider") == ("expired",)
    assert states.allowed_targets("snoozed", origin="user") == ("expired", "suggested")


def test_the_undo_window_is_sixty_seconds():
    changed = datetime(2026, 10, 14, 9, 0, 0, tzinfo=UTC)
    assert states.undo_window_open(changed, changed + timedelta(seconds=60))
    assert not states.undo_window_open(changed, changed + timedelta(seconds=61))


def test_no_action_leaves_the_state_machine_through_a_back_door():
    """From every state, every action either lands on a known state or raises: nothing returns an unknown state."""
    for state in TASK_STATES:
        for action in states.ACTIONS:
            try:
                out = states.transition(state, action, prev_state="suggested", origin="user")
            except (states.InvalidTransition, states.UndoExpired):
                continue
            assert out in TASK_STATES
