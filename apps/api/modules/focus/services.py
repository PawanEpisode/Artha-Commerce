"""
Writes for the Pomodoro timer (F-01.1). The server is the clock: a phase is a start time, a planned length and a pause
total, and every transition is applied lazily under a row lock (`_settle`) whenever the timer is read or acted on, so
nothing depends on a worker running at the moment a phase ends.

Finished rounds are written through `tracking.services.record_session` (idempotent on `client_id`, forwarded to
coverage). This module never touches tracking tables.

Every action that can change the live timer is wrapped with `events.announces`, which emits one `timer_changed` after
commit when the timer's `client_id` or `version` moved. `update_settings` is deliberately not announcing: a running
phase snapshots its lengths and flags when it begins, so a settings change can never move a running end.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime

from django.db import IntegrityError, transaction

from modules.tracking import selectors as tracking_selectors
from modules.tracking import services as tracking
from modules.tracking.domain import durations

from . import selectors
from .domain import timing
from .domain.timing import TimingError
from .errors import ConflictError, InvalidInput, NotFoundError
from .events import announces
from .models import ActiveTimer, FocusSettings

logger = logging.getLogger(__name__)
BREAKS = ("short_break", "long_break")


def _now() -> datetime:
    return tracking._now()


# --- Settings -------------------------------------------------------------------------------------------------
def get_or_create_settings(user_id) -> FocusSettings:
    settings, _ = FocusSettings.objects.get_or_create(pk=user_id)
    return settings


def _match_preset(d: dict) -> str:
    for key, preset in timing.PRESETS.items():
        if all(d[k] == v for k, v in preset.items()):
            return key
    return "custom"


@transaction.atomic
def update_settings(user_id, changes: dict) -> tuple[FocusSettings, list[str]]:
    """Returns (settings, names of the fields that changed) so the caller can report the analytics event."""
    s = FocusSettings.objects.select_for_update().filter(pk=user_id).first() or get_or_create_settings(user_id)
    changed: list[str] = []
    try:
        if "preset" in changes:
            d = timing.resolve_preset(changes["preset"], {**selectors.settings_dict(s), **changes})
            durations_now = {k: getattr(s, k) for k in d}
            if d != durations_now or s.last_preset != changes["preset"]:
                for k, v in d.items():
                    setattr(s, k, v)
                s.last_preset = changes["preset"]
                changed.append("preset")
        else:
            keys = [k for k in timing.PRESETS["classic"] if k in changes]
            if keys:
                merged = {k: changes.get(k, getattr(s, k)) for k in timing.PRESETS["classic"]}
                d = timing.validate_durations(merged)
                if any(getattr(s, k) != d[k] for k in keys):
                    for k, v in d.items():
                        setattr(s, k, v)
                    s.last_preset = _match_preset(d)
                    changed.append("durations")
    except TimingError as exc:
        raise InvalidInput(exc.args[0], {exc.field or "detail": [exc.args[0]]}) from None
    for key in (
        "auto_start_breaks",
        "auto_start_focus",
        "overtime_enabled",
        "sound_enabled",
        "notifications_enabled",
        "intro_seen",
    ):
        if key in changes and getattr(s, key) != changes[key]:
            setattr(s, key, changes[key])
            changed.append(key)
    if "volume" in changes and s.volume != changes["volume"]:
        s.volume = changes["volume"]
        changed.append("volume")
    s.save()
    return s, changed


# --- Internals ------------------------------------------------------------------------------------------------
def _lock(user_id) -> ActiveTimer | None:
    return ActiveTimer.objects.select_for_update().filter(pk=user_id).first()


def _child_id(timer: ActiveTimer, label: str) -> uuid.UUID:
    return uuid.uuid5(timer.client_id, label)


def _remember(user_id, *, cycle_id, cycle_round: int, next_phase: str, at: datetime) -> None:
    s = FocusSettings.objects.select_for_update().filter(pk=user_id).first() or get_or_create_settings(user_id)
    s.cycle_id, s.cycle_round, s.cycle_next_phase, s.cycle_updated_at = cycle_id, cycle_round, next_phase, at
    s.save(update_fields=["cycle_id", "cycle_round", "cycle_next_phase", "cycle_updated_at", "updated_at"])


def _stale(timer: ActiveTimer, now) -> ConflictError:
    return ConflictError(
        "The timer changed on another device.", {"timer": selectors.timer_dict(timer, now)}, code="stale_version"
    )


def _record_round(timer: ActiveTimer, *, ended_at, focus_seconds, status="completed", reason="", **flags):
    """Writes the finished round. A live-timer overlap or a duplicate is logged, never raised: a read must not fail."""
    try:
        tracking.record_session(
            timer.user_id,
            source="pomodoro",
            started_at=timer.started_at,
            ended_at=ended_at,
            focus_seconds=focus_seconds,
            subject_id=timer.subject_id,
            chapter_id=timer.chapter_id,
            activity_type=timer.activity_type,
            client_id=timer.client_id,
            paused_total_seconds=durations.span_seconds(durations.whole_seconds(timer.started_at), ended_at)
            - focus_seconds,
            pause_count=timer.pause_count,
            planned_seconds=timer.planned_seconds,
            round_number=timer.round_number,
            cycle_id=timer.cycle_id,
            status=status,
            interruption_reason=reason,
            **flags,
        )
        return True
    except (ConflictError, InvalidInput):
        logger.warning("Pomodoro round could not be saved (user %s)", timer.user_id, exc_info=True)
        return False


def _begin(timer: ActiveTimer, *, phase, round_number, cycle_id, at, label) -> ActiveTimer:
    d = {
        "focus_minutes": timer.focus_minutes,
        "short_break_minutes": timer.short_break_minutes,
        "long_break_minutes": timer.long_break_minutes,
    }
    timer.phase, timer.round_number, timer.cycle_id = phase, round_number, cycle_id
    timer.planned_seconds = timing.planned_seconds(phase, d)
    timer.started_at, timer.paused_at = durations.whole_seconds(at), None
    timer.paused_total_seconds = timer.pause_count = timer.extension_count = 0
    timer.away_pending = False
    timer.client_id = _child_id(timer, label)
    timer.version += 1
    timer.save()
    return timer


def _after_focus(timer: ActiveTimer, end_at) -> ActiveTimer | None:
    """A counted focus round is over: start its break, or wait for the student to."""
    kind = timing.break_after(timer.round_number, timer.rounds_before_long)
    _remember(timer.user_id, cycle_id=timer.cycle_id, cycle_round=timer.round_number, next_phase=kind, at=end_at)
    if timer.auto_start_breaks:
        return _begin(
            timer,
            phase=kind,
            round_number=timer.round_number,
            cycle_id=timer.cycle_id,
            at=end_at,
            label=f"{kind}-{timer.round_number}",
        )
    timer.delete()
    return None


def _after_break(timer: ActiveTimer, end_at) -> ActiveTimer | None:
    """A break is over (ran out or skipped). Focus starts on its own only if asked to and the student is there."""
    long_done = timer.phase == "long_break"
    cycle_id = None if long_done else timer.cycle_id
    cycle_round = 0 if long_done else timer.round_number
    _remember(timer.user_id, cycle_id=cycle_id, cycle_round=cycle_round, next_phase="focus", at=end_at)
    if timer.auto_start_focus and timing.was_present(timer.last_seen_at, end_at):
        round_number = cycle_round + 1
        return _begin(
            timer,
            phase="focus",
            round_number=round_number,
            cycle_id=cycle_id or uuid.uuid4(),
            at=end_at,
            label=f"focus-{round_number}",
        )
    timer.delete()
    return None


def _settle(timer: ActiveTimer | None, now: datetime, *, present: bool = False) -> ActiveTimer | None:
    """
    Applies every transition that is due by `now` and returns the timer that remains (None when idle). `present` says the
    student's own screen reported the end (so the round counts without the two-minute presence check).
    """
    for _ in range(8):
        if timer is None or timer.away_pending:
            return timer
        if not timing.finished(
            timer.planned_seconds, timer.started_at, now, timer.paused_at, timer.paused_total_seconds
        ):
            return timer
        end_at = timing.phase_end_at(timer.started_at, timer.planned_seconds, timer.paused_total_seconds)
        if timer.phase == "focus":
            if not (present or timing.was_present(timer.last_seen_at, end_at)):
                timer.away_pending = True
                timer.version += 1
                timer.save()
                return timer
            if timer.overtime_enabled:
                # Past the planned length the round keeps counting until the student stops it. It only closes by
                # itself when they have gone (or the extra time hits its cap), at the last time they were seen.
                if timing.overtime_holds(end_at, timer.last_seen_at, now):
                    return timer
                stop = durations.whole_seconds(timing.overtime_stop(end_at, timer.last_seen_at))
                counted = timing.elapsed(timer.started_at, stop, None, timer.paused_total_seconds)
                _record_round(timer, ended_at=stop, focus_seconds=max(counted, timer.planned_seconds), auto_closed=True)
                timer = _after_focus(timer, stop)
            else:
                _record_round(timer, ended_at=end_at, focus_seconds=timer.planned_seconds, auto_closed=not present)
                timer = _after_focus(timer, end_at)
        else:
            timer = _after_break(timer, end_at)
        present = False
    return timer


def _current(user_id, now, version=None, *, present=False) -> ActiveTimer | None:
    timer = _settle(_lock(user_id), now, present=present)
    if timer and version is not None and timer.version != version:
        raise _stale(timer, now)
    return timer


def _require(timer: ActiveTimer | None) -> ActiveTimer:
    if not timer:
        raise NotFoundError("No timer is running.")
    return timer


def _bump(timer: ActiveTimer, now: datetime) -> ActiveTimer:
    timer.version += 1
    timer.last_seen_at = now
    timer.save()
    return timer


# --- Actions --------------------------------------------------------------------------------------------------
@transaction.atomic
@announces
def sync(user_id, *, alive: bool = False) -> ActiveTimer | None:
    """What a page loads or polls. `alive` is the heartbeat; it never changes `version`."""
    now = _now()
    timer = _settle(_lock(user_id), now)
    if timer and alive:
        timer.last_seen_at = now
        timer.save(update_fields=["last_seen_at", "updated_at"])
    return timer


@transaction.atomic
@announces
def start(
    user_id,
    *,
    client_id,
    phase: str = "focus",
    preset: str | None = None,
    custom: dict | None = None,
    subject_id=None,
    chapter_id=None,
    activity_type: str | None = None,
    at: datetime | None = None,
) -> tuple[ActiveTimer, bool]:
    """Starts a focus round (or the break that is due). Returns (timer, created); a retried start is a no-op."""
    now = _now()
    timer = _current(user_id, now)
    if timer:
        if timer.client_id == client_id:
            return timer, False
        raise ConflictError(
            "A timer is already running.",
            {"live": "pomodoro", "timer": selectors.timer_dict(timer, now)},
            code="timer_already_active",
        )
    if tracking_selectors.session_by_client_id(user_id, client_id):
        raise ConflictError("That round has already finished.", code="client_id_used")
    if tracking.live_timer_kind(user_id) != "none":
        raise ConflictError(
            "The stopwatch is running.", {"live": tracking.live_timer_kind(user_id)}, code="timer_already_active"
        )
    settings = get_or_create_settings(user_id)
    if preset:
        settings, _ = update_settings(user_id, {"preset": preset, **(custom or {})})
    idle = selectors.idle_dict(settings, now)
    if phase != "focus" and idle["next_phase"] != phase:
        raise InvalidInput("No break is due.", code="no_break_due")
    if phase != "focus":
        round_number, cycle_id = idle["next_round"], idle["cycle_id"]
    elif idle["next_phase"] != "focus":  # starting a round instead of the due break skips the break
        n = idle["next_round"] + 1
        round_number, cycle_id = (1, uuid.uuid4()) if n > settings.rounds_before_long else (n, idle["cycle_id"])
    else:
        round_number, cycle_id = idle["next_round"], idle["cycle_id"] or uuid.uuid4()
    subject, chapter = tracking._resolve_tags(subject_id, chapter_id)
    started = durations.whole_seconds(durations.clamp_client_time(at, now))
    d = {k: getattr(settings, k) for k in timing.PRESETS["classic"]}
    try:
        with transaction.atomic():
            timer = ActiveTimer.objects.create(
                user_id=user_id,
                phase=phase,
                round_number=round_number,
                cycle_id=cycle_id,
                planned_seconds=timing.planned_seconds(phase, d),
                started_at=started,
                last_seen_at=now,
                preset=settings.last_preset,
                auto_start_breaks=settings.auto_start_breaks,
                auto_start_focus=settings.auto_start_focus,
                overtime_enabled=settings.overtime_enabled,
                subject=subject,
                chapter=chapter,
                activity_type=tracking._check_activity(
                    activity_type or tracking.get_or_create_settings(user_id).default_activity_type
                ),
                client_id=client_id,
                **d,
            )
    except IntegrityError:
        raise ConflictError("A timer is already running.", {"live": "pomodoro"}, code="timer_already_active") from None
    return timer, True


@transaction.atomic
@announces
def pause(user_id, *, version=None, at: datetime | None = None) -> ActiveTimer:
    now = _now()
    timer = _require(_current(user_id, now, version))
    if timer.phase != "focus" or timer.away_pending:
        raise ConflictError("Only a running focus round can be paused.", code="not_pausable")
    if timer.paused_at:
        return timer
    timer.paused_at = max(timer.started_at, min(durations.clamp_client_time(at, now), now))
    timer.pause_count += 1
    return _bump(timer, now)


@transaction.atomic
@announces
def resume(user_id, *, version=None, at: datetime | None = None) -> ActiveTimer:
    now = _now()
    timer = _require(_current(user_id, now, version))
    if not timer.paused_at:
        return timer
    resumed = max(timer.paused_at, min(durations.clamp_client_time(at, now), now))
    timer.paused_total_seconds += durations.span_seconds(timer.paused_at, resumed)
    timer.paused_at = None
    return _bump(timer, now)


@transaction.atomic
@announces
def extend(user_id, *, version=None) -> ActiveTimer:
    now = _now()
    timer = _require(_current(user_id, now, version))
    if timer.phase != "focus" or timer.away_pending:
        raise ConflictError("Only a focus round can be extended.", code="not_extendable")
    if (
        timer.overtime_enabled
        and timing.elapsed(timer.started_at, now, timer.paused_at, timer.paused_total_seconds) >= timer.planned_seconds
    ):
        raise ConflictError("The round is already running past its planned length.", code="not_extendable")
    if timer.extension_count >= timing.MAX_EXTENSIONS:
        raise ConflictError("A round can be extended three times.", code="extension_limit")
    if timer.planned_seconds + timing.EXTEND_SECONDS > timing.PLANNED_MAX_SECONDS:
        raise ConflictError("That round cannot get any longer.", code="extension_limit")
    timer.planned_seconds += timing.EXTEND_SECONDS
    timer.extension_count += 1
    return _bump(timer, now)


@transaction.atomic
@announces
def complete(user_id, *, version=None) -> ActiveTimer | None:
    """
    The student's own screen reached zero. The round counts without the presence check. A little clock disagreement is
    tolerated; a call that is early by more than that is refused.
    """
    now = _now()
    timer = _lock(user_id)
    if timer and timer.phase == "focus" and timer.overtime_enabled and not timer.away_pending:
        # Nothing closes at zero any more: the student's own Stop and save does. Reaching zero only shows they are here.
        timer.last_seen_at = now
        timer.save(update_fields=["last_seen_at", "updated_at"])
        return _settle(timer, now)
    if timer and not timer.away_pending:
        due = timing.phase_end_at(timer.started_at, timer.planned_seconds, timer.paused_total_seconds)
        if timer.paused_at is None and 0 < (due - now).total_seconds() <= timing.COMPLETE_TOLERANCE_SECONDS:
            now = due
        elif timer.paused_at is not None or now < due:
            if version is not None and timer.version != version:
                raise _stale(timer, now)
            raise ConflictError("That phase has not finished yet.", code="not_finished")
    return _settle(timer, now, present=True)


@transaction.atomic
@announces
def skip_break(user_id, *, version=None) -> ActiveTimer | None:
    now = _now()
    timer = _require(_current(user_id, now, version))
    if timer.phase not in BREAKS:
        raise ConflictError("There is no break to skip.", code="not_a_break")
    timer.last_seen_at = now
    return _after_break(timer, now)


@transaction.atomic
@announces
def end(
    user_id, *, client_id=None, version=None, save: bool = True, reason: str = ""
) -> tuple[object | None, str, ActiveTimer | None]:
    """
    Ends a focus round. Returns (session, outcome, timer). Before the planned length it is an early end ("saved",
    "too_short" or "discarded") and nothing follows. Once the round has reached its planned length (overtime) saving it
    completes the round at the full counted time and the break that is due starts (`timer`), or waits when breaks do
    not start on their own.
    """
    now = _now()
    if reason and reason not in timing.REASONS:
        raise InvalidInput("Unknown reason.", {"reason": ["Pick one of the listed reasons."]})
    timer = _lock(user_id)
    if not timer:
        existing = tracking_selectors.session_by_client_id(user_id, client_id)
        if existing:
            return existing, "saved", _settle(_lock(user_id), now)
        raise NotFoundError("No timer is running.")
    timer = _settle(timer, now)
    if timer is None or timer.phase != "focus" or timer.away_pending:
        # A retried end whose first attempt went through: the round is saved, and what runs now is whatever followed.
        existing = tracking_selectors.session_by_client_id(user_id, client_id) if client_id else None
        if existing:
            return existing, "saved", timer
        raise _stale(timer, now) if timer else NotFoundError("No timer is running.")
    if version is not None and timer.version != version:
        raise _stale(timer, now)
    stop = timer.paused_at or now
    counted = timing.elapsed(timer.started_at, now, timer.paused_at, timer.paused_total_seconds)
    session = None
    outcome = "discarded"
    if save and timer.overtime_enabled and counted >= timer.planned_seconds:
        ended = durations.whole_seconds(stop)
        counted = min(counted, timer.planned_seconds + timing.OVERTIME_MAX_SECONDS)
        if _record_round(timer, ended_at=ended, focus_seconds=counted, status="completed", auto_closed=False):
            session = tracking_selectors.session_by_client_id(user_id, timer.client_id)
            return session, "completed", _after_focus(timer, ended)
    if save and counted >= timing.MIN_ROUND_SECONDS:
        ended = durations.whole_seconds(stop)
        ok = _record_round(
            timer, ended_at=ended, focus_seconds=counted, status="partial", reason=reason, auto_closed=False
        )
        outcome = "saved" if ok else "discarded"
        if ok:
            session = tracking_selectors.session_by_client_id(user_id, timer.client_id)
    elif save:
        outcome = "too_short"
    _remember(user_id, cycle_id=timer.cycle_id, cycle_round=timer.round_number - 1, next_phase="focus", at=now)
    timer.delete()
    return session, outcome, None


@transaction.atomic
@announces
def claim(user_id, *, count: bool, version=None) -> tuple[ActiveTimer | None, str]:
    """The student answers "did you study through that round?" after being away. Returns (timer, outcome)."""
    now = _now()
    timer = _settle(_lock(user_id), now)
    if not timer or not timer.away_pending:
        return timer, "none"
    if version is not None and timer.version != version:
        raise _stale(timer, now)
    end_at = timing.phase_end_at(timer.started_at, timer.planned_seconds, timer.paused_total_seconds)
    if not count:
        _remember(user_id, cycle_id=timer.cycle_id, cycle_round=timer.round_number - 1, next_phase="focus", at=now)
        timer.delete()
        return None, "discarded"
    _record_round(
        timer,
        ended_at=end_at,
        focus_seconds=timer.planned_seconds,
        auto_closed=False,
        presence_verified=False,
    )
    timer.away_pending = False
    timer = _after_focus(timer, end_at)
    return _settle(timer, now), "counted"


@transaction.atomic
@announces
def change_context(user_id, *, version, changes: dict) -> ActiveTimer:
    now = _now()
    timer = _require(_current(user_id, now, version))
    if "subject_id" in changes or "chapter_id" in changes:
        subject, chapter = tracking._resolve_tags(
            changes.get("subject_id", timer.subject_id), changes.get("chapter_id", timer.chapter_id)
        )
        timer.subject, timer.chapter = subject, chapter
    if "activity_type" in changes:
        timer.activity_type = tracking._check_activity(changes["activity_type"])
    return _bump(timer, now)


# --- Data rights ----------------------------------------------------------------------------------------------
@transaction.atomic
@announces
def delete_all_for_user(user_id) -> dict:
    """Removes the timer and timer settings. Finished rounds are tracking sessions and go with the tracking data."""
    ActiveTimer.objects.filter(pk=user_id).delete()
    FocusSettings.objects.filter(pk=user_id).delete()
    return {}
