"""
Closed sets used across the module. Pure Python (no Django): models build their `choices` from these, services and
tests compare against them, so a value is spelled in exactly one place.
"""

from __future__ import annotations

from enum import StrEnum


class Channel(StrEnum):
    PUSH = "push"
    EMAIL = "email"
    INBOX = "inbox"


# Channels a delivery row can record (the inbox is the notification row itself).
DELIVERY_CHANNELS = (Channel.PUSH, Channel.EMAIL)


class PermissionState(StrEnum):
    NOT_ASKED = "not_asked"
    PRE_PROMPT_SHOWN = "pre_prompt_shown"
    GRANTED = "granted"
    DENIED = "denied"
    DISMISSED = "dismissed"
    SKIPPED_INSTALL = "skipped_install"
    UNSUPPORTED = "unsupported"


# States that mean the student has made a decision (the onboarding step counts as satisfied).
DECIDED_STATES = frozenset(
    {
        PermissionState.GRANTED,
        PermissionState.DENIED,
        PermissionState.DISMISSED,
        PermissionState.SKIPPED_INSTALL,
        PermissionState.UNSUPPORTED,
    }
)


class PermissionSource(StrEnum):
    ONBOARDING = "onboarding"
    FOLLOWUP = "followup"
    SETTINGS = "settings"


class Tone(StrEnum):
    CALM = "calm"
    DRIVEN = "driven"
    CELEBRATORY = "celebratory"


class MessageStatus(StrEnum):
    """Life of a motivation message. Only `published` ones are ever picked; a draft is never shown or sent."""

    DRAFT = "draft"
    PUBLISHED = "published"
    RETIRED = "retired"


class MessagePhase(StrEnum):
    """How close the student's exam is. `any` fits every day; the others only fit their window (see `motivation`)."""

    FAR = "far"
    NEAR = "near"
    FINAL_WEEK = "final_week"
    EXAM_DAY = "exam_day"
    ANY = "any"


class ShownChannel(StrEnum):
    """Where the day's message was first used. The first one wins the day (`messageshown` is unique per day)."""

    INAPP = "inapp"
    PUSH = "push"


class DeviceKind(StrEnum):
    WEB_PUSH = "web_push"
    DESKTOP_APP = "desktop_app"


class DevicePlatform(StrEnum):
    ANDROID = "android"
    IOS = "ios"
    WINDOWS = "windows"
    MACOS = "macos"
    LINUX = "linux"
    OTHER = "other"


class DeviceBrowser(StrEnum):
    CHROME = "chrome"
    EDGE = "edge"
    FIREFOX = "firefox"
    SAFARI = "safari"
    OTHER = "other"


class DisplayMode(StrEnum):
    BROWSER = "browser"
    STANDALONE = "standalone"
    APP = "app"


class RevokeReason(StrEnum):
    GONE = "gone"  # the push service answered 404 or 410
    FAILURES = "failures"
    USER_REMOVED = "user_removed"
    SIGNED_OUT = "signed_out"
    ACCOUNT_ERASED = "account_erased"


class JobKind(StrEnum):
    TIMER_END = "timer_end"
    STOPWATCH_LONG = "stopwatch_long"
    DELIVER_DEFERRED = "deliver_deferred"


class JobStatus(StrEnum):
    PENDING = "pending"
    FIRED = "fired"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"
    FAILED = "failed"


class SkipReason(StrEnum):
    CHANGED = "changed"
    PAUSED = "paused"
    GONE = "gone"
    FLAG_OFF = "flag_off"
    DISABLED = "disabled"
    STALE = "stale"


class DeliveryStatus(StrEnum):
    QUEUED = "queued"
    SENT = "sent"
    FAILED = "failed"
    SUPPRESSED = "suppressed"


class SuppressReason(StrEnum):
    PREFERENCE = "preference"
    QUIET_HOURS = "quiet_hours"
    CAP = "cap"
    NO_DEVICE = "no_device"
    STALE = "stale"
    VISITED_TODAY = "visited_today"
    FLAG_OFF = "flag_off"
    NO_ADDRESS = "no_address"  # email: the student has no address on file


class ButtonAction(StrEnum):
    """What a button on a timer alert does (W3.6, FR-N12). The meaning of each lives in `focus`."""

    PAUSE = "pause"
    RESUME = "resume"
    START_BREAK = "start_break"
    START_FOCUS = "start_focus"


def choices(enum_class: type[StrEnum]) -> list[tuple[str, str]]:
    """Django `choices` for a model field."""
    return [(member.value, member.value) for member in enum_class]


def values(enum_class: type[StrEnum]) -> list[str]:
    return [member.value for member in enum_class]
