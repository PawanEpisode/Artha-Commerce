"""
Tests for session domain logic: state transitions, deadline calculations, and shuffling.
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from modules.practice.domain.session import (
    calculate_deadline,
    feedback_policy_for_mode,
    shuffle_options,
    validate_transition,
)
from modules.practice.models import Session


def test_validate_transition_valid():
    validate_transition(Session.Status.CREATED, Session.Status.IN_PROGRESS)
    validate_transition(Session.Status.IN_PROGRESS, Session.Status.PAUSED)
    validate_transition(Session.Status.PAUSED, Session.Status.IN_PROGRESS)
    validate_transition(Session.Status.IN_PROGRESS, Session.Status.SUBMITTED)
    validate_transition(Session.Status.PAUSED, Session.Status.AUTO_SUBMITTED)


def test_validate_transition_invalid():
    with pytest.raises(ValueError):
        validate_transition(Session.Status.SUBMITTED, Session.Status.IN_PROGRESS)
    with pytest.raises(ValueError):
        validate_transition(Session.Status.ABANDONED, Session.Status.PAUSED)
    with pytest.raises(ValueError):
        validate_transition(Session.Status.CREATED, Session.Status.PAUSED)


def test_calculate_deadline():
    now = datetime(2026, 10, 15, 10, 0, 0, tzinfo=UTC)
    # 60 minutes limit, 0 paused -> exactly 11:00
    d1 = calculate_deadline(now, time_limit_seconds=3600, paused_total_seconds=0)
    assert d1 == datetime(2026, 10, 15, 11, 0, 0, tzinfo=UTC)

    # 60 minutes limit, 300s (5 mins) paused -> 11:05
    d2 = calculate_deadline(now, time_limit_seconds=3600, paused_total_seconds=300)
    assert d2 == datetime(2026, 10, 15, 11, 5, 0, tzinfo=UTC)

    # Untimed session has no deadline
    d3 = calculate_deadline(now, time_limit_seconds=None, paused_total_seconds=0)
    assert d3 is None


def test_feedback_policy_for_mode():
    assert feedback_policy_for_mode("exam", "instant") == Session.FeedbackPolicy.NEVER_UNTIL_SUBMIT
    assert feedback_policy_for_mode("untimed", "instant") == Session.FeedbackPolicy.INSTANT
    assert feedback_policy_for_mode("chapter_quiz", "instant") == Session.FeedbackPolicy.INSTANT
    assert feedback_policy_for_mode("custom_test", "at_end") == Session.FeedbackPolicy.AT_END


def test_shuffle_options_preserves_pinned():
    o1, o2, o3, o4 = uuid4(), uuid4(), uuid4(), uuid4()
    options = [
        {"id": o1, "pinned": False, "body_md": "Option A"},
        {"id": o2, "pinned": False, "body_md": "Option B"},
        {"id": o3, "pinned": False, "body_md": "Option C"},
        {"id": o4, "pinned": True, "body_md": "All of the above"},  # Pinned at index 3
    ]

    shuffled = shuffle_options(options, seed=42)
    # Length is preserved
    assert len(shuffled) == 4
    # Pinned option stays at index 3
    assert shuffled[3]["id"] == o4
    # All option ids are present
    shuffled_ids = {opt["id"] for opt in shuffled}
    assert shuffled_ids == {o1, o2, o3, o4}
