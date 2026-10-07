"""
The one list of what we can tell a student: categories (what the student switches on and off) and events (what
actually happens, with its priority and idempotency key). Adding a notification means adding an entry here, a copy
builder in `copy.py` and tests; caps, quiet hours and preferences then apply to it automatically.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import timedelta
from enum import StrEnum

from .enums import Channel


class Category(StrEnum):
    TIMER = "timer"
    TRACKER = "tracker"
    REVISION = "revision"
    PLAN = "plan"
    CONTENT = "content"
    EVALUATION = "evaluation"
    EXAM = "exam"
    PROGRESS = "progress"
    MOTIVATION = "motivation"
    SYSTEM = "system"  # not switchable by the student (the test push); never listed in CATEGORIES
    DIGEST = "digest"  # the daily digest (W3.7): its switch is `NotificationSettings.digest_enabled`, not a category


class UnknownEvent(KeyError):
    """An event key that is not in the catalogue."""


class UnknownSwitch(ValueError):
    """A category and channel pair the student cannot switch."""


@dataclass(frozen=True)
class CategorySpec:
    key: Category
    label: str
    description: str
    default_channels: frozenset[Channel]


@dataclass(frozen=True)
class EventSpec:
    key: str
    category: Category
    priority: int  # 0 exempt from quiet hours and the daily cap, 3 lowest
    dedupe_template: str  # filled with `dedupe.build_dedupe_key`
    expires_after: timedelta | None = None  # how long a held or late notification stays worth sending
    skip_if_opened: bool = False  # not worth a push when the student already opened the app today (FR-N10)

    @property
    def exempt(self) -> bool:
        return self.priority == 0

    @property
    def system(self) -> bool:
        """
        System events answer a direct request of the student (the test push, the digest they chose), so category
        switches do not apply to them. The master switch, quiet hours and the cap still do (by priority).
        """
        return self.category in (Category.SYSTEM, Category.DIGEST)


_PUSH_AND_INBOX = frozenset({Channel.PUSH, Channel.INBOX})

CATEGORIES: tuple[CategorySpec, ...] = (
    CategorySpec(Category.TIMER, "Timer alerts", "When a focus round or break ends.", _PUSH_AND_INBOX),
    CategorySpec(Category.TRACKER, "Study tracker", "Long-running stopwatch, daily goal and streak.", _PUSH_AND_INBOX),
    CategorySpec(Category.REVISION, "Revision", "Chapters that are due for revision.", _PUSH_AND_INBOX),
    CategorySpec(Category.PLAN, "Today's plan", "Your plan for the day, when it is ready.", _PUSH_AND_INBOX),
    CategorySpec(Category.CONTENT, "New content", "New amendments, tests and papers for your course.", _PUSH_AND_INBOX),
    CategorySpec(
        Category.EVALUATION, "Answer evaluation", "When an evaluation of your answer is ready.", _PUSH_AND_INBOX
    ),
    CategorySpec(Category.EXAM, "Exam countdown", "Milestones on the way to your exam date.", _PUSH_AND_INBOX),
    CategorySpec(
        Category.PROGRESS,
        "Weekly summary",
        "A weekly look at your study time.",
        frozenset({Channel.EMAIL, Channel.INBOX}),
    ),
    CategorySpec(
        Category.MOTIVATION, "Daily thought", "A short nudge on days you have not opened Artha.", _PUSH_AND_INBOX
    ),
)

_HOUR = timedelta(hours=1)

_EVENT_LIST: tuple[EventSpec, ...] = (
    EventSpec("timer_end", Category.TIMER, 0, "timer_end:{client_id}:{version}"),
    EventSpec("break_over", Category.TIMER, 0, "timer_end:{client_id}:{version}"),
    EventSpec("stopwatch_long", Category.TRACKER, 1, "stopwatch_long:{client_id}", expires_after=_HOUR),
    EventSpec("goal_reached", Category.TRACKER, 1, "goal:{local_date}", expires_after=6 * _HOUR),
    EventSpec("streak_at_risk", Category.TRACKER, 1, "streak:{local_date}", expires_after=3 * _HOUR),
    EventSpec(
        "daily_nudge", Category.MOTIVATION, 3, "nudge:{local_date}", expires_after=6 * _HOUR, skip_if_opened=True
    ),
    EventSpec(
        "revision_due", Category.REVISION, 2, "revision:{local_date}", expires_after=12 * _HOUR, skip_if_opened=True
    ),
    EventSpec("exam_milestone", Category.EXAM, 2, "exam:{days_left}", expires_after=12 * _HOUR),
    EventSpec("content_published", Category.CONTENT, 3, "content:{item_id}", expires_after=24 * _HOUR),
    EventSpec("evaluation_ready", Category.EVALUATION, 1, "evaluation:{attempt_id}", expires_after=24 * _HOUR),
    EventSpec("plan_ready", Category.PLAN, 2, "plan:{local_date}", expires_after=12 * _HOUR),
    EventSpec("weekly_summary", Category.PROGRESS, 3, "weekly:{iso_week}", expires_after=24 * _HOUR),
    # W3.7: one push a day at the nudge time for a student who chose the digest (FR-N34) instead of separate alerts.
    EventSpec("daily_digest", Category.DIGEST, 3, "digest:{local_date}", expires_after=6 * _HOUR),
)

EVENTS: Mapping[str, EventSpec] = {spec.key: spec for spec in _EVENT_LIST}

#: Events the student triggers directly. Exempt from quiet hours and the cap, not behind a category switch, and each
#: one is unique (the dedupe key carries a nonce) so pressing "Send me a test" twice sends twice.
SYSTEM_EVENTS: Mapping[str, EventSpec] = {
    "test_push": EventSpec("test_push", Category.SYSTEM, 0, "test_push:{nonce}"),
}
_CATEGORY_BY_KEY: Mapping[Category, CategorySpec] = {spec.key: spec for spec in CATEGORIES}

Overrides = Mapping[tuple[str, str], bool]


def get_event(key: str) -> EventSpec:
    spec = EVENTS.get(key) or SYSTEM_EVENTS.get(key)
    if spec is None:
        raise UnknownEvent(key)
    return spec


def category_spec(category: str) -> CategorySpec:
    try:
        return _CATEGORY_BY_KEY[Category(category)]
    except (ValueError, KeyError):  # not a category, or a system one the student cannot switch
        raise UnknownSwitch(f"Unknown category: {category}") from None


def category_label(category: str) -> str:
    """The student-facing name of a category; the system one (the test push) reads "Test"."""
    try:
        return category_spec(category).label
    except UnknownSwitch:
        if category == Category.DIGEST:
            return "Daily digest"
        return "Test" if category == Category.SYSTEM else "Notification"


def is_default_enabled(category: str, channel: str) -> bool:
    return Channel(channel) in category_spec(category).default_channels


def validate_switch(category: str, channel: str) -> tuple[Category, Channel]:
    """The pair a student may switch, or `UnknownSwitch`."""
    spec = category_spec(category)
    try:
        return spec.key, Channel(channel)
    except ValueError:
        raise UnknownSwitch(f"Unknown channel: {channel}") from None


def is_enabled(category: str, channel: str, overrides: Overrides) -> bool:
    """The student's override when there is one, else the default from the catalogue."""
    key = (str(category), str(channel))
    if key in overrides:
        return overrides[key]
    return is_default_enabled(category, channel)
