"""
Onboarding as a pure state machine (PRD 5.2, ERD 5.11). Every step says how to tell it is done from FACTS (the owning
table), so a stored flag can never mark someone complete with missing data. No Django, no I/O: the selector loads
the rows once and passes them in as `Facts`.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

#: Raise when a release adds a step (give that step `since` = the new number). A step only applies once the version
#: reaches its `since`. Optional steps never re-prompt a student who already completed an earlier version.
#: 3 = the push-notification `alerts` step (X-01.1, W2.5).
ONBOARDING_VERSION = 3


class StepState(StrEnum):
    TODO = "todo"
    DONE = "done"
    SKIPPED = "skipped"
    UNAVAILABLE = "unavailable"


class Status(StrEnum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


@dataclass(frozen=True)
class Stored:
    """What `profiles_onboarding` keeps: no derived facts, only order and the answers that have no table of their own."""

    completed_version: int = 0
    started: bool = False
    items: dict[str, dict] = field(default_factory=dict)

    def state(self, key: str) -> str | None:
        return (self.items.get(key) or {}).get("state")


@dataclass(frozen=True)
class Facts:
    """The rows already loaded for the bootstrap (no extra queries) plus a flag lookup. Duck-typed on purpose."""

    user_id: Any
    profile: Any
    enrollment: Any | None
    settings: Any | None
    stored: Stored
    flag: Callable[[str], bool] = lambda _name: True  # noqa: E731


@dataclass(frozen=True)
class StepSpec:
    key: str
    order: int
    mandatory: bool
    since: int
    is_satisfied: Callable[[Facts], bool]
    available: Callable[[Facts], bool] = lambda _facts: True  # noqa: E731


@dataclass(frozen=True)
class StepView:
    key: str
    state: StepState
    mandatory: bool
    since: int


@dataclass(frozen=True)
class Resolution:
    status: Status
    mode: str  # "full" for a new student, "update" for one who completed an earlier version
    next_step: str | None
    missing: list[str]
    steps: list[StepView]
    completed_version: int
    required_version: int


def _stored_done(key: str) -> Callable[[Facts], bool]:
    return lambda facts: facts.stored.state(key) == "done"


# --- the built-in steps. Others (coaching from F-12, planner from F-13) register through `profiles.registry`. ---------

PROFILE = StepSpec("profile", 10, True, 2, lambda f: bool((f.profile.full_name or "").strip()))
COURSE = StepSpec("course", 20, True, 1, lambda f: f.enrollment is not None)
HOURS = StepSpec("hours", 30, True, 2, lambda f: f.enrollment is not None and f.enrollment.planned_minutes is not None)
TARGETS = StepSpec(
    "targets",
    40,
    True,
    2,
    lambda f: f.settings is not None and f.settings.targets_confirmed_at is not None,
    available=lambda f: f.flag("study_targets"),
)
CATCHUP = StepSpec("catchup", 50, False, 1, _stored_done("catchup"))
AVATAR = StepSpec("avatar", 70, False, 2, lambda f: f.profile.avatar_kind != "initials")

BUILT_IN_STEPS = (PROFILE, COURSE, HOURS, TARGETS, CATCHUP, AVATAR)


def step_state(spec: StepSpec, facts: Facts) -> StepState:
    if not spec.available(facts):
        return StepState.UNAVAILABLE
    if spec.is_satisfied(facts):
        return StepState.DONE
    if facts.stored.state(spec.key) == "skipped":
        return StepState.SKIPPED
    return StepState.TODO


def resolve(specs: list[StepSpec], facts: Facts, required_version: int = ONBOARDING_VERSION) -> Resolution:
    """
    - Mandatory steps that apply to this version and are not satisfied block completion, always (facts over flags).
    - A new student (`full` mode) is walked through unseen optional steps after the mandatory ones; a student who
      completed an earlier version (`update` mode) sees only what is missing. A skipped optional step is offered once
      more from the workspace "Finish your setup" card, never as a blocker.
    - Every mandatory step satisfied but `completed_version` behind: `in_progress` with nothing to show. The web calls
      complete silently (the backfilled student after a version bump that added no mandatory step).
    """
    ordered = sorted(specs, key=lambda s: s.order)
    views = [StepView(s.key, step_state(s, facts), s.mandatory, s.since) for s in ordered]
    state_of = {v.key: v.state for v in views}
    applies = [s for s in ordered if s.since <= required_version and state_of[s.key] is not StepState.UNAVAILABLE]
    missing = [s.key for s in applies if s.mandatory and state_of[s.key] is not StepState.DONE]
    mode = "update" if facts.stored.completed_version > 0 else "full"
    optional = [s.key for s in applies if not s.mandatory and state_of[s.key] is StepState.TODO]

    if not missing and facts.stored.completed_version >= required_version:
        status = Status.COMPLETED
    elif not facts.stored.started and missing:
        status = Status.NOT_STARTED
    else:
        status = Status.IN_PROGRESS

    next_step = None
    if status is not Status.COMPLETED:
        next_step = missing[0] if missing else (optional[0] if mode == "full" and optional else None)
    return Resolution(status, mode, next_step, missing, views, facts.stored.completed_version, required_version)
