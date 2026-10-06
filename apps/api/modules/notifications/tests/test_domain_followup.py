"""The follow-up ask rule (W2.5b): who may be asked again, and when."""

from datetime import UTC, datetime, timedelta

import pytest

from modules.notifications.domain.enums import PermissionState
from modules.notifications.domain.followup import FOLLOWUP_INTERVAL, MAX_ASKS, followup_due

NOW = datetime(2026, 10, 20, 12, 0, tzinfo=UTC)


def due(state="dismissed", asks=1, asked=NOW - timedelta(days=15), decided=NOW - timedelta(days=15)):
    return followup_due(state, asks, asked, decided, NOW)


def test_the_interval_and_cap_are_the_ones_in_the_prd():
    assert FOLLOWUP_INTERVAL == timedelta(days=14) and MAX_ASKS == 3


def test_a_student_who_said_not_now_is_asked_again_after_fourteen_days():
    assert due() is True
    assert due(asked=NOW - FOLLOWUP_INTERVAL, decided=NOW - FOLLOWUP_INTERVAL) is True  # exactly 14 days
    assert due(asked=NOW - timedelta(days=13, hours=23), decided=NOW - timedelta(days=20)) is False


def test_the_clock_runs_from_the_later_of_the_last_ask_and_the_last_answer():
    assert due(asked=NOW - timedelta(days=30), decided=NOW - timedelta(days=2)) is False
    assert due(asked=NOW - timedelta(days=2), decided=NOW - timedelta(days=30)) is False


def test_only_two_follow_ups_after_the_first_ask():
    assert due(asks=1) is True and due(asks=2) is True
    assert due(asks=3) is False


@pytest.mark.parametrize(
    "state",
    [s.value for s in PermissionState if s is not PermissionState.DISMISSED],
)
def test_nothing_but_not_now_is_ever_nagged(state):
    # granted needs nothing; denied/blocked, unsupported and missing install are explained in Settings, never nagged
    assert due(state=state) is False


def test_a_dismissal_with_no_recorded_ask_or_time_is_due():
    assert followup_due("dismissed", 0, None, None, NOW) is True
