"""
The one place that decides whether a push goes out now, later, or not at all. Pure: every fact it needs is passed in
(preferences, devices, how many pushes were already sent today), so every rule is a plain unit test.

Order of the rules matters and is part of the contract:
  1. the event or the whole feature is switched off          -> suppress (flag_off)
  2. the student switched the category, channel or master off -> suppress (preference)
  3. the student has no device to reach                       -> suppress (no_device)
  4. exempt events (timer) are sent at once, unless they are too late to be useful -> send or suppress (stale)
  5. other events past their useful life                      -> suppress (stale)
  6. inside quiet hours                                       -> defer to the end of the window, or suppress when it would expire first
  7. the daily cap is used up                                 -> suppress (cap)
  8. otherwise                                                -> send
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta
from enum import StrEnum

from .catalogue import EventSpec
from .enums import SuppressReason
from .quiet_hours import in_quiet_hours, quiet_window_end

DAILY_CAP = 3  # non-exempt pushes a student can receive in one local day
PRIORITY_ONE_EXTRA = 1  # priority 0 and 1 events may use one slot beyond the cap (PRD Q4)
EXEMPT_STALE_AFTER = timedelta(minutes=5)  # a round-end alert older than this is no longer useful


class Action(StrEnum):
    SEND = "send"
    DEFER = "defer"
    SUPPRESS = "suppress"


@dataclass(frozen=True)
class QuietPreference:
    enabled: bool
    timezone: str
    start: time
    end: time


@dataclass(frozen=True)
class PolicyInput:
    spec: EventSpec
    now: datetime
    master_on: bool
    channel_enabled: bool
    has_active_device: bool
    quiet: QuietPreference | None
    sent_today: int  # pushes that count towards the cap already sent in the student's local day
    event_disabled: bool = False  # kill switch for the event or the feature, decided by the caller
    intended_at: datetime | None = None  # when the moment happened (a timer end); None means now
    expires_at: datetime | None = None


@dataclass(frozen=True)
class Decision:
    action: Action
    reason: SuppressReason | None = None
    deliver_at: datetime | None = None


def _suppress(reason: SuppressReason) -> Decision:
    return Decision(Action.SUPPRESS, reason=reason)


def decide(facts: PolicyInput) -> Decision:
    if facts.event_disabled:
        return _suppress(SuppressReason.FLAG_OFF)
    if not facts.master_on or not facts.channel_enabled:
        return _suppress(SuppressReason.PREFERENCE)
    if not facts.has_active_device:
        return _suppress(SuppressReason.NO_DEVICE)

    if facts.spec.exempt:
        late = facts.intended_at is not None and facts.now - facts.intended_at > EXEMPT_STALE_AFTER
        return _suppress(SuppressReason.STALE) if late else Decision(Action.SEND)

    if facts.expires_at is not None and facts.now >= facts.expires_at:
        return _suppress(SuppressReason.STALE)

    quiet = facts.quiet
    if quiet and quiet.enabled and in_quiet_hours(facts.now, quiet.timezone, quiet.start, quiet.end):
        window_end = quiet_window_end(facts.now, quiet.timezone, quiet.start, quiet.end)
        if facts.expires_at is not None and facts.expires_at <= window_end:
            return _suppress(SuppressReason.QUIET_HOURS)
        return Decision(Action.DEFER, deliver_at=window_end)

    limit = DAILY_CAP + (PRIORITY_ONE_EXTRA if facts.spec.priority <= 1 else 0)
    if facts.sent_today >= limit:
        return _suppress(SuppressReason.CAP)
    return Decision(Action.SEND)
