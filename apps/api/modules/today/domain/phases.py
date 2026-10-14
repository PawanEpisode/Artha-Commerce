"""Exam phase from the days left, and the multipliers each phase puts on the five kinds of work (PRD 5.5). Pure."""

from __future__ import annotations

from datetime import date

from .constants import GROUPS

#: Upper bound of days_to_exam (inclusive) for each phase, checked in order. `post_exam` is zero or negative.
_BUILD_FROM = 91
_CONSOLIDATE_FROM = 31
_SPRINT_FROM = 11

MULTIPLIERS: dict[str, dict[str, int]] = {
    #               learn revise practice exam news
    "steady": {"learn": 100, "revise": 100, "practice": 100, "exam": 100, "news": 100},
    "build": {"learn": 130, "revise": 80, "practice": 100, "exam": 60, "news": 100},
    "consolidate": {"learn": 100, "revise": 120, "practice": 120, "exam": 90, "news": 110},
    "sprint": {"learn": 60, "revise": 130, "practice": 120, "exam": 130, "news": 140},
    "final": {"learn": 20, "revise": 150, "practice": 100, "exam": 130, "news": 150},
}


def days_to_exam(exam_date: date | None, local_date: date) -> int | None:
    """Calendar days from the student's local date to the target date (negative once it has passed); None without a date."""
    if exam_date is None:
        return None
    return (exam_date - local_date).days


def phase_for(days: int | None) -> str:
    if days is None:
        return "steady"
    if days <= 0:
        return "post_exam"
    if days >= _BUILD_FROM:
        return "build"
    if days >= _CONSOLIDATE_FROM:
        return "consolidate"
    if days >= _SPRINT_FROM:
        return "sprint"
    return "final"


def multiplier(phase: str, group: str) -> int:
    """Percent weight of a kind group in a phase. `post_exam` has no plan, so asking for it is a bug, not a default."""
    if group not in GROUPS:
        raise ValueError(f"unknown kind group {group!r}")
    try:
        return MULTIPLIERS[phase][group]
    except KeyError as exc:
        raise ValueError(f"no multipliers for phase {phase!r}") from exc
