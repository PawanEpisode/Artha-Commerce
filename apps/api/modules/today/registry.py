"""
The provider registry and the contract every module follows to put tasks in a student's Today list (ERD 3.2).

A leaf module: types and registration only, no Django models, safe to import from any app's `AppConfig.ready()`. Today imports no
provider code; an owning module calls `register_task_provider(...)` once and appears in Today without a change here.

    from modules.today.registry import KindSpec, ProviderResult, TaskCandidate, register_task_provider

Rules every provider must pass (a contract test per provider enforces them): pure read, deterministic for the same request,
within its timeout, only papers in `ctx.papers`, a `dedupe_key` that is stable across days for the same unit of work, plain-text
titles, allow-listed links, honest signals 0..100, and it never decides how many tasks are shown (it offers candidates and, when
there are many, a `backlog_count`).
"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Literal
from uuid import UUID

from .domain.constants import GROUPS, SLOTS

Group = Literal["learn", "revise", "practice", "exam", "news"]
Slot = Literal[
    "mcq", "formula", "section", "practical", "revision", "recall", "read", "amendment", "challenge", "custom", "other"
]

_NAME = re.compile(r"^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+$")
_KIND = re.compile(r"^[a-z][a-z0-9_]{0,39}$")
_CODE = re.compile(r"^[a-z][a-z0-9_]{0,39}$")


# ---- what a provider offers -------------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class KindSpec:
    name: str  # "revise_chapter", "mcq_set", "recall_cards", ... globally unique
    group: Group  # which phase multiplier applies
    slot: Slot  # which tile slot it fills (one task per slot per paper)
    icon: str  # a key in the design-system icon map
    default_est_minutes: int


@dataclass(frozen=True)
class DeepLink:
    path: str  # "/app/revision"; must match the allow-list in `domain/deeplinks.py`
    search: Mapping[str, str | int] = field(default_factory=dict)  # flat, scalar values, each at most 200 characters


@dataclass(frozen=True)
class Signals:
    """Integers 0..100. The provider says how it looks; Today decides the weight."""

    urgency: int  # how overdue or time-bound (revision overdue days, amendment close to the attempt)
    importance: int  # marks weight, historical frequency, priority chapter
    weakness: int  # low accuracy, forgotten cards
    freshness: int  # how long since the student touched this area


@dataclass(frozen=True)
class ManualActionRef:
    key: str  # "coverage.log_revision": looked up in the registry when the student ticks the task by hand
    label: str  # "Also log this revision"
    default_on: bool = True


@dataclass(frozen=True)
class TaskCandidate:
    kind: str  # one of the provider's declared KindSpec names
    dedupe_key: str  # stable for the same unit of work across days, at most 120 characters
    title: str  # plain text, at most 80 characters, no HTML
    reason_code: str  # from the reason registry
    reason: str  # at most 140 characters, a human sentence ("Revision 2 was due 3 days ago")
    link: DeepLink
    est_minutes: int  # 1..90
    signals: Signals
    subject_id: UUID | None = None  # None = the General pool
    chapter_id: UUID | None = None
    target_value: int | None = None  # for count tasks (5 MCQs)
    must_do: bool = False  # rare: an overdue milestone, an amendment for an attempt within 14 days
    expires_on: date | None = None  # not offered after this local date (the daily challenge: today)
    payload: Mapping[str, Any] = field(default_factory=dict)  # at most 2 KB, schema-versioned by the provider
    manual_action: ManualActionRef | None = None


# ---- what Today tells a provider --------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class EnrollmentCtx:
    id: UUID
    scheme_id: UUID
    course_code: str
    level_code: str
    exam_date: date | None
    term_code: str | None
    daily_hours: Any | None  # Decimal


@dataclass(frozen=True)
class PaperCtx:
    subject_id: UUID
    key: str
    name: str
    paper_number: int | None
    kind: str
    coverage_pct: int
    days_untouched: int | None


@dataclass(frozen=True)
class PlanContext:
    user_id: UUID
    local_date: date
    tz: str
    enrollment: EnrollmentCtx | None
    days_to_exam: int | None
    phase: str
    papers: tuple[PaperCtx, ...]  # active, not excluded, in the student's scheme and electives
    done_keys: frozenset[str]
    suppressed_keys: frozenset[str]
    budget_minutes: int
    comeback: bool
    seed: int
    is_preview: bool


@dataclass(frozen=True)
class TaskRequest:
    ctx: PlanContext
    limit: int
    deadline_ms: int


@dataclass(frozen=True)
class ProviderResult:
    candidates: Sequence[TaskCandidate]
    backlog_count: int = 0  # how many more the student has than the candidates (38 overdue revisions)
    backlog_label: str = ""  # "revisions are overdue"
    backlog_link: DeepLink | None = None  # "/app/revision"


# ---- completion, reconcile, manual action -----------------------------------------------------------------------------------


@dataclass(frozen=True)
class Event:
    """A domain event as the completion rules see it (the payload is the emitter's, validated by its schema)."""

    name: str
    key: str  # the event's idempotency key (session id, ledger event id)
    user_id: UUID
    occurred_at: datetime
    payload: Mapping[str, Any]


@dataclass(frozen=True)
class TaskView:
    """Plain data of one task, so a rule or a provider never touches a model."""

    id: UUID
    kind: str
    dedupe_key: str
    local_date: date
    state: str
    subject_id: UUID | None
    chapter_id: UUID | None
    target_value: int | None
    progress_value: int
    payload: Mapping[str, Any]


@dataclass(frozen=True)
class Match:
    evidence_key: str  # the event's key: the idempotency anchor
    done: bool = False  # exact completion
    delta: int = 0  # progress toward target_value (answered questions, reviewed cards)


@dataclass(frozen=True)
class CompletionRule:
    event_name: str
    match: Callable[[Event, TaskView], Match | None]  # PURE: no I/O, no clock; runs inline (budget 5 ms per task)


@dataclass(frozen=True)
class Evidence:
    done: bool
    progress: int | None
    key: str


@dataclass(frozen=True)
class ManualAction:
    key: str
    label: str
    default_on: bool
    run: Callable[
        [UUID, TaskView], None
    ]  # idempotent: derive client_id = uuid5(NS, str(task.id)); never raise on replay


# ---- registration -----------------------------------------------------------------------------------------------------------

ProvideFn = Callable[[TaskRequest], ProviderResult]
ReconcileFn = Callable[[UUID, Sequence[TaskView], date], Mapping[UUID, Evidence]]


@dataclass(frozen=True)
class ProviderSpec:
    name: str
    provide: ProvideFn
    kinds: tuple[KindSpec, ...]
    label: str
    flag: str | None
    timeout_ms: int
    max_candidates: int
    enabled_for: Callable[[UUID], bool] | None
    completion: tuple[CompletionRule, ...]
    reconcile: ReconcileFn | None
    manual_actions: tuple[ManualAction, ...]


#: Reason codes (ERD 3.6) with the label "Why this?" falls back to when a provider's own text is missing.
BUILTIN_REASONS: dict[str, str] = {
    "revision_overdue": "A revision is overdue",
    "revision_due_today": "A revision is due today",
    "recall_due": "Cards are due for recall",
    "weak_topic": "This is a weak area for you",
    "high_yield": "This area carries many marks",
    "amendment_new": "There is a new amendment",
    "not_practised_yet": "You have not practised this yet",
    "next_in_syllabus": "Next in your syllabus",
    "starved_paper": "This paper has had no activity for a few days",
    "daily_challenge": "Today's challenge",
    "milestone_behind": "Your plan is behind on this",
    "comeback": "A lighter day to restart",
    "custom": "Added by you",
}

TIMEOUT_MIN_MS, TIMEOUT_MAX_MS = 100, 2000
MAX_CANDIDATES_MIN, MAX_CANDIDATES_MAX = 1, 50

_providers: dict[str, ProviderSpec] = {}
_hooks: list[Callable[[], None]] = []
_reasons: dict[str, str] = dict(BUILTIN_REASONS)


class RegistrationError(ValueError):
    """A provider or reason that breaks the contract. Raised at start-up, so a bad registration fails loudly in CI, not in a plan."""


def register_task_provider(
    name: str,
    provide: ProvideFn,
    *,
    kinds: Sequence[KindSpec],
    label: str,
    flag: str | None = None,
    timeout_ms: int = 400,
    max_candidates: int = 20,
    enabled_for: Callable[[UUID], bool] | None = None,
    completion: Sequence[CompletionRule] = (),
    reconcile: ReconcileFn | None = None,
    manual_actions: Sequence[ManualAction] = (),
) -> None:
    """Install (or replace, `AppConfig.ready` can run twice) the provider `name`, spelled `<module>.<what>`."""
    if not _NAME.match(name):
        raise RegistrationError(f"provider name {name!r} must look like '<module>.<what>'")
    if not kinds:
        raise RegistrationError(f"provider {name} declares no kinds")
    if not label.strip():
        raise RegistrationError(f"provider {name} needs a label")
    if not TIMEOUT_MIN_MS <= timeout_ms <= TIMEOUT_MAX_MS:
        raise RegistrationError(f"provider {name}: timeout_ms must be {TIMEOUT_MIN_MS} to {TIMEOUT_MAX_MS}")
    if not MAX_CANDIDATES_MIN <= max_candidates <= MAX_CANDIDATES_MAX:
        raise RegistrationError(f"provider {name}: max_candidates must be {MAX_CANDIDATES_MIN} to {MAX_CANDIDATES_MAX}")

    own_kinds: set[str] = set()
    for spec in kinds:
        if not _KIND.match(spec.name):
            raise RegistrationError(f"kind name {spec.name!r} is not a lower_snake name")
        if spec.group not in GROUPS:
            raise RegistrationError(f"kind {spec.name}: unknown group {spec.group!r}")
        if spec.slot not in SLOTS:
            raise RegistrationError(f"kind {spec.name}: unknown slot {spec.slot!r}")
        if spec.name in own_kinds:
            raise RegistrationError(f"provider {name} declares kind {spec.name} twice")
        own_kinds.add(spec.name)
    for other in _providers.values():
        clash = own_kinds & {k.name for k in other.kinds}
        if other.name != name and clash:
            raise RegistrationError(f"kind(s) {sorted(clash)} already belong to provider {other.name}")

    manual_keys = [m.key for m in manual_actions]
    if len(set(manual_keys)) != len(manual_keys):
        raise RegistrationError(f"provider {name} declares a manual action twice")

    _providers[name] = ProviderSpec(
        name=name,
        provide=provide,
        kinds=tuple(kinds),
        label=label,
        flag=flag,
        timeout_ms=timeout_ms,
        max_candidates=max_candidates,
        enabled_for=enabled_for,
        completion=tuple(completion),
        reconcile=reconcile,
        manual_actions=tuple(manual_actions),
    )
    for hook in list(_hooks):
        hook()  # e.g. Today subscribes to the events a new provider's completion rules name


def add_register_hook(fn: Callable[[], None]) -> None:
    """Called after every registration. Idempotent. Providers register from other apps' `ready()`, in any order."""
    if fn not in _hooks:
        _hooks.append(fn)


def register_reason(code: str, *, label: str) -> None:
    """Extend the reason registry. Re-registering a code with a different label is a mistake, not an override."""
    if not _CODE.match(code) or not label.strip():
        raise RegistrationError(f"reason {code!r} needs a lower_snake code and a label")
    if code in _reasons and _reasons[code] != label:
        raise RegistrationError(f"reason {code!r} is already registered with another label")
    _reasons[code] = label


# ---- reads (used by Today itself) -------------------------------------------------------------------------------------------


def providers() -> list[ProviderSpec]:
    """Every registered provider, in name order (so generation is deterministic)."""
    return [_providers[name] for name in sorted(_providers)]


def get_provider(name: str) -> ProviderSpec | None:
    return _providers.get(name)


def kind_spec(kind: str) -> tuple[ProviderSpec, KindSpec] | None:
    for spec in providers():
        for k in spec.kinds:
            if k.name == kind:
                return spec, k
    return None


def reasons() -> dict[str, str]:
    return dict(_reasons)


def reason_label(code: str) -> str:
    return _reasons.get(code, _reasons["custom"])


def completion_event_names() -> list[str]:
    """The union of event names named by providers' completion rules: what Today subscribes to (done once at start)."""
    return sorted({rule.event_name for spec in providers() for rule in spec.completion})


def manual_action(key: str) -> tuple[ProviderSpec, ManualAction] | None:
    for spec in providers():
        for action in spec.manual_actions:
            if action.key == key:
                return spec, action
    return None


def clear() -> None:
    """Test helper."""
    _providers.clear()
    _reasons.clear()
    _reasons.update(BUILTIN_REASONS)
