"""
Tests for mocktest clock domain logic.
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
import pytest

from modules.mocktest.domain import clock


def test_calculate_extra_seconds():
    # 3 hours (10800s) with 25% accommodation = 2700s
    assert clock.calculate_extra_seconds(10800, 25) == 2700
    assert clock.calculate_extra_seconds(10800, 0) == 0
    assert clock.calculate_extra_seconds(100, 10) == 10


def test_clock_instructions_phase():
    now = datetime(2026, 10, 20, 10, 0, 0, tzinfo=timezone.utc)
    state = clock.state_at(
        phase="instructions",
        instructions_accepted_at=None,
        reading_seconds=900,
        reading_ends_at=None,
        writing_started_at=None,
        writing_ends_at=None,
        upload_until=None,
        duration_seconds=10800,
        extra_seconds=0,
        paused_seconds=0,
        is_paused=False,
        now=now,
    )
    assert state.phase == "instructions"
    assert state.remaining_ms == 10800 * 1000
    assert not state.auto_submit_due


def test_clock_reading_phase():
    accepted_at = datetime(2026, 10, 20, 10, 0, 0, tzinfo=timezone.utc)
    reading_ends = accepted_at + timedelta(seconds=900)  # 15 mins
    now = accepted_at + timedelta(seconds=300)  # 5 mins in

    state = clock.state_at(
        phase="reading",
        instructions_accepted_at=accepted_at,
        reading_seconds=900,
        reading_ends_at=reading_ends,
        writing_started_at=None,
        writing_ends_at=None,
        upload_until=None,
        duration_seconds=10800,
        extra_seconds=0,
        paused_seconds=0,
        is_paused=False,
        now=now,
    )
    assert state.phase == "reading"
    assert state.remaining_ms == 600 * 1000  # 10 minutes remaining in reading


def test_clock_reading_period_ends_transitions_to_writing():
    accepted_at = datetime(2026, 10, 20, 10, 0, 0, tzinfo=timezone.utc)
    reading_ends = accepted_at + timedelta(seconds=900)
    now = accepted_at + timedelta(seconds=901)  # reading just ended

    state = clock.state_at(
        phase="reading",
        instructions_accepted_at=accepted_at,
        reading_seconds=900,
        reading_ends_at=reading_ends,
        writing_started_at=None,
        writing_ends_at=None,
        upload_until=None,
        duration_seconds=10800,
        extra_seconds=0,
        paused_seconds=0,
        is_paused=False,
        now=now,
    )
    assert state.phase == "writing"
    assert state.remaining_ms > 0


def test_clock_writing_phase_and_grace():
    w_start = datetime(2026, 10, 20, 10, 0, 0, tzinfo=timezone.utc)
    w_end = w_start + timedelta(seconds=10800)

    # 1. Active writing
    now_active = w_start + timedelta(seconds=3600)  # 1 hour in
    state_active = clock.state_at(
        phase="writing",
        instructions_accepted_at=w_start,
        reading_seconds=0,
        reading_ends_at=None,
        writing_started_at=w_start,
        writing_ends_at=w_end,
        upload_until=None,
        duration_seconds=10800,
        extra_seconds=0,
        paused_seconds=0,
        is_paused=False,
        now=now_active,
    )
    assert state_active.phase == "writing"
    assert state_active.remaining_ms == 7200 * 1000
    assert not state_active.auto_submit_due

    # 2. Overdue past grace (120s)
    now_overdue = w_end + timedelta(seconds=125)
    state_overdue = clock.state_at(
        phase="writing",
        instructions_accepted_at=w_start,
        reading_seconds=0,
        reading_ends_at=None,
        writing_started_at=w_start,
        writing_ends_at=w_end,
        upload_until=None,
        duration_seconds=10800,
        extra_seconds=0,
        paused_seconds=0,
        is_paused=False,
        now=now_overdue,
    )
    assert state_overdue.remaining_ms == 0
    assert state_overdue.auto_submit_due is True
