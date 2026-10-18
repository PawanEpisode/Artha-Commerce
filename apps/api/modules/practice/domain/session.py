"""
Pure session lifecycle, shuffling, and deadline calculation logic (F-06 ERD 2.19, 3.5).
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta
from typing import Any

# Valid status transitions
VALID_TRANSITIONS: dict[str, set[str]] = {
    "created": {"in_progress", "submitted", "abandoned"},
    "in_progress": {"paused", "submitted", "auto_submitted", "abandoned"},
    "paused": {"in_progress", "submitted", "auto_submitted", "abandoned"},
    "submitted": set(),
    "auto_submitted": set(),
    "abandoned": set(),
}


def validate_transition(current_status: str, target_status: str) -> None:
    """Validate session lifecycle transition."""
    allowed = VALID_TRANSITIONS.get(current_status, set())
    if target_status not in allowed:
        raise ValueError(f"Invalid session status transition from '{current_status}' to '{target_status}'.")


def pause_allowed(mode: str, spec: dict[str, Any] | None) -> bool:
    """Exam simulations and sessions created with `allow_pause: false` (timed past papers) cannot be paused."""
    return mode != "exam" and bool((spec or {}).get("allow_pause", True))


def calculate_deadline(
    started_at: datetime | None,
    time_limit_seconds: int | None,
    paused_total_seconds: int = 0,
) -> datetime | None:
    """Calculate session deadline."""
    if not started_at or time_limit_seconds is None:
        return None
    return started_at + timedelta(seconds=time_limit_seconds + paused_total_seconds)


def feedback_policy_for_mode(mode: str, requested: str | None = None) -> str:
    """Determine feedback policy based on session mode and request."""
    if mode == "exam":
        return "never_until_submit"
    if requested in ("instant", "after_section", "at_end", "never_until_submit"):
        return requested
    if mode == "revision":
        return "instant"
    if mode == "untimed":
        return "instant"
    return "at_end"


def shuffle_options(options: list[dict[str, Any]], seed: int, position: int = 1) -> list[dict[str, Any]]:
    """
    Deterministically shuffle options using seed and question position.
    Pinned options (pinned=True) remain at their fixed original index positions.
    """
    if not options or len(options) <= 1:
        return list(options)

    # Separate pinned and unpinned
    pinned_indices = {i for i, opt in enumerate(options) if opt.get("pinned", False)}
    unpinned_items = [opt for i, opt in enumerate(options) if i not in pinned_indices]

    # Deterministic shuffle
    rng = random.Random(seed ^ (position * 10007))
    rng.shuffle(unpinned_items)

    result: list[dict[str, Any]] = []
    unpinned_iter = iter(unpinned_items)
    for i, orig_opt in enumerate(options):
        if i in pinned_indices:
            result.append(orig_opt)
        else:
            result.append(next(unpinned_iter))

    return result
