"""
Activity targets and the 50% confidence gate as pure functions (no Django, no I/O). F-16 section 5.10.

Counts are facts and targets are goals: the ledger and the counters keep everything that was logged, and these rules
only decide whether one more MANUAL log is accepted and what a screen should show. Mirrored in TypeScript
(`apps/web/src/modules/coverage/lib/rules.ts`) and tested against `tests/fixtures/rules_cases.json`.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

#: A chapter must be at least this covered before the student can rate their confidence in it.
CONFIDENCE_MIN_PCT = 50

#: Ledger event type -> (activity key, counter attribute on ChapterProgress, plural label used in messages).
CAPPED_ACTIVITIES = {
    "practice_done": ("practice", "practice_count", "Practice sets"),
    "revision_done": ("revisions", "revision_count", "Revision rounds"),
    "mock_done": ("mocks", "mock_count", "Mock tests"),
}


#: Student targets are goals per chapter, 0 to 10 each. 0 means "I do not track this activity".
TARGET_MIN = 0
TARGET_MAX = 10


@dataclass(frozen=True)
class Targets:
    """What the student wants to finish in every chapter (F-16 S2). Applies to every chapter of every paper."""

    practice_sets: int = 1
    revisions: int = 2
    mocks: int = 1

    def for_event_type(self, event_type: str) -> int:
        return {"practice": self.practice_sets, "revisions": self.revisions, "mocks": self.mocks}[
            CAPPED_ACTIVITIES[event_type][0]
        ]

    def as_tuple(self) -> tuple[int, int, int]:
        return (self.practice_sets, self.revisions, self.mocks)


#: The values every student had before F-16 (they came from the syllabus table). Nothing changes on deploy.
DEFAULT_TARGETS = Targets()

PRESET_CUSTOM = "custom"

#: Light, Standard and Intense. `[CALIBRATE]` with tutors (PRD Q-F16-1). The web renders these from the API.
PRESETS: dict[str, Targets] = {
    "light": Targets(1, 1, 1),
    "standard": Targets(2, 2, 2),
    "intense": Targets(3, 3, 3),
}
PRESET_LABELS = {"light": "Light", "standard": "Standard", "intense": "Intense", PRESET_CUSTOM: "Custom"}


class Direction(StrEnum):
    SAME = "same"
    RAISED = "raised"
    LOWERED = "lowered"
    MIXED = "mixed"


def targets_valid(value: Targets) -> bool:
    return all(isinstance(n, int) and TARGET_MIN <= n <= TARGET_MAX for n in value.as_tuple())


def preset_for(value: Targets) -> str:
    """The preset these numbers equal, else `custom`. Derived on every save, so it can never disagree with the numbers."""
    for key, preset in PRESETS.items():
        if preset == value:
            return key
    return PRESET_CUSTOM


def direction_of(old: Targets, new: Targets) -> Direction:
    pairs = list(zip(old.as_tuple(), new.as_tuple(), strict=True))
    up = any(n > o for o, n in pairs)
    down = any(n < o for o, n in pairs)
    if up and down:
        return Direction.MIXED
    if up:
        return Direction.RAISED
    return Direction.LOWERED if down else Direction.SAME


@dataclass(frozen=True)
class Impact:
    """How many chapter percentages a change of targets moves. `dropping` is what the web warns about."""

    chapters_changed: int = 0
    chapters_dropping: int = 0
    chapters_rising: int = 0


def impact_of(changes: list[tuple[int, int]]) -> Impact:
    """`changes` is (old_pct, new_pct) per chapter."""
    moved = [(o, n) for o, n in changes if o != n]
    return Impact(
        chapters_changed=len(moved),
        chapters_dropping=sum(1 for o, n in moved if n < o),
        chapters_rising=sum(1 for o, n in moved if n > o),
    )


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
