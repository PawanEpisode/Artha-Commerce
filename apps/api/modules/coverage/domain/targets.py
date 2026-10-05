"""
Activity targets and the 50% confidence gate as pure functions (no Django, no I/O). F-16 section 5.10.

Counts are facts and targets are goals: the ledger and the counters keep everything that was logged, and these rules
only decide whether one more MANUAL log is accepted and what a screen should show. Mirrored in TypeScript
(`apps/web/src/modules/coverage/lib/rules.ts`) and tested against `tests/fixtures/rules_cases.json`.
"""

from __future__ import annotations

from enum import StrEnum

#: A chapter must be at least this covered before the student can rate their confidence in it.
CONFIDENCE_MIN_PCT = 50

#: Ledger event type -> (activity key, counter attribute on ChapterProgress, plural label used in messages).
CAPPED_ACTIVITIES = {
    "practice_done": ("practice", "practice_count", "Practice sets"),
    "revision_done": ("revisions", "revision_count", "Revision rounds"),
    "mock_done": ("mocks", "mock_count", "Mock tests"),
}


class Decision(StrEnum):
    OK = "ok"
    AT_TARGET = "at_target"
    NOT_TRACKED = "not_tracked"


def can_log(*, count: int, add: int = 1, target: int) -> Decision:
    """
    A target of 0 means "not tracked". A request that would go past the target is refused whole (never clipped), so
    counts already above the target (legacy data) simply block any further manual log.
    """
    if target <= 0:
        return Decision.NOT_TRACKED
    if count + max(add, 1) > target:
        return Decision.AT_TARGET
    return Decision.OK


def confidence_allowed(coverage_pct: int) -> bool:
    return coverage_pct >= CONFIDENCE_MIN_PCT


def activity_progress(count: int, target: int) -> dict:
    """What a screen shows for one activity: never more than the target as `done`, the real count as `logged`."""
    done = min(count, target) if target > 0 else 0
    return {
        "done": done,
        "target": target,
        "logged": count,
        "can_log": can_log(count=count, add=1, target=target) is Decision.OK,
    }
