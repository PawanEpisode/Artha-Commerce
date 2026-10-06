"""Reads for the Pomodoro timer. Every function takes `user_id`; another student's row is never found."""

from __future__ import annotations

from datetime import datetime

from modules.tracking import services as tracking

from .domain import judgement, timing
from .domain.judgement import TimerEndJudgement
from .models import ActiveTimer, FocusSettings


def get_timer(user_id) -> ActiveTimer | None:
    return ActiveTimer.objects.filter(pk=user_id).first()


def get_settings(user_id) -> FocusSettings | None:
    return FocusSettings.objects.filter(pk=user_id).first()


def settings_or_default(user_id) -> FocusSettings:
    return get_settings(user_id) or FocusSettings(user_id=user_id)


def live_kind(user_id) -> str | None:
    """The live-timer provider tracking asks. A break that has already run out no longer blocks a stopwatch."""
    timer = get_timer(user_id)
    if not timer:
        return None
    if timer.phase != "focus" and timing.finished(
        timer.planned_seconds, timer.started_at, tracking._now(), None, timer.paused_total_seconds
    ):
        return None
    return "pomodoro"


def live_end_at(timer: ActiveTimer) -> datetime | None:
    """When the phase reaches its planned end, or None while it cannot (paused, or the round already ended away)."""
    if timer.paused_at is not None or timer.away_pending:
        return None
    return timing.phase_end_at(timer.started_at, timer.planned_seconds, timer.paused_total_seconds)


def timer_end_judgement(
    user_id, client_id, expected_version: int, now: datetime, *, planned_end: datetime | None = None
) -> TimerEndJudgement:
    """
    Is the end of timer (`client_id`, `expected_version`) still real? Read-only (PRD FR-N18): one plain SELECT, no lock,
    no `_settle`, no `sync`, so asking never changes the timer row. The answer comes from timestamps alone.
    """
    row = (
        ActiveTimer.objects.filter(pk=user_id)
        .values(
            "client_id",
            "version",
            "phase",
            "started_at",
            "planned_seconds",
            "paused_at",
            "paused_total_seconds",
            "away_pending",
            "overtime_enabled",
        )
        .first()
    )
    facts = judgement.TimerFacts(**row) if row else None
    return judgement.judge_timer_end(
        facts, client_id=client_id, expected_version=expected_version, now=now, planned_end=planned_end
    )


def timer_dict(timer: ActiveTimer, now: datetime) -> dict:
    elapsed = timing.elapsed(timer.started_at, now, timer.paused_at, timer.paused_total_seconds)
    running = timer.paused_at is None
    overtime = timer.phase == "focus" and timer.overtime_enabled and not timer.away_pending
    extra = timing.overtime_seconds(elapsed, timer.planned_seconds) if overtime else 0
    return {
        "phase": timer.phase,
        "status": "away" if timer.away_pending else "paused" if timer.paused_at else "running",
        "round_number": timer.round_number,
        "rounds_before_long": timer.rounds_before_long,
        "cycle_id": timer.cycle_id,
        "preset": timer.preset,
        "planned_seconds": timer.planned_seconds,
        "elapsed_seconds": min(elapsed, timer.planned_seconds),
        "remaining_seconds": timing.remaining(
            timer.planned_seconds, timer.started_at, now, timer.paused_at, timer.paused_total_seconds
        ),
        "extension_count": timer.extension_count,
        "overtime_enabled": timer.overtime_enabled,
        # Seconds counted beyond the planned length; the round keeps running until the student stops it.
        "overtime_seconds": min(extra, timing.OVERTIME_MAX_SECONDS),
        "can_extend": timer.phase == "focus"
        and not timer.away_pending
        and not (overtime and elapsed >= timer.planned_seconds)
        and timer.extension_count < timing.MAX_EXTENSIONS,
        "started_at": timer.started_at,
        "paused_at": timer.paused_at,
        "paused_total_seconds": timer.paused_total_seconds,
        "pause_count": timer.pause_count,
        "ends_at": timing.phase_end_at(timer.started_at, timer.planned_seconds, timer.paused_total_seconds)
        if running
        else None,
        "last_seen_at": timer.last_seen_at,
        "away_pending": timer.away_pending,
        "auto_start_breaks": timer.auto_start_breaks,
        "auto_start_focus": timer.auto_start_focus,
        "subject_id": timer.subject_id,
        "chapter_id": timer.chapter_id,
        "activity_type": timer.activity_type,
        "client_id": timer.client_id,
        "version": timer.version,
    }


def idle_dict(settings: FocusSettings, now: datetime) -> dict:
    """What "Start" will do when no phase is running: continue the remembered cycle or begin round 1."""
    fresh = timing.cycle_fresh(settings.cycle_updated_at, now) and settings.cycle_id is not None
    if fresh and settings.cycle_next_phase != "focus":
        phase, round_number = settings.cycle_next_phase, settings.cycle_round
    elif fresh and 0 < settings.cycle_round < settings.rounds_before_long:
        phase, round_number = "focus", settings.cycle_round + 1
    else:
        phase, round_number, fresh = "focus", 1, False
    return {
        "next_phase": phase,
        "next_round": round_number,
        "rounds_before_long": settings.rounds_before_long,
        "cycle_id": settings.cycle_id if fresh else None,
    }


def settings_dict(s: FocusSettings) -> dict:
    return {
        "preset": s.last_preset,
        "focus_minutes": s.focus_minutes,
        "short_break_minutes": s.short_break_minutes,
        "long_break_minutes": s.long_break_minutes,
        "rounds_before_long": s.rounds_before_long,
        "auto_start_breaks": s.auto_start_breaks,
        "auto_start_focus": s.auto_start_focus,
        "overtime_enabled": s.overtime_enabled,
        "sound_enabled": s.sound_enabled,
        "volume": s.volume,
        "notifications_enabled": s.notifications_enabled,
        "intro_seen": s.intro_seen,
    }


def export_all(user_id) -> dict:
    out = {"settings": None, "timer": None}
    for key, obj in (("settings", get_settings(user_id)), ("timer", get_timer(user_id))):
        if obj is not None:
            out[key] = {
                f.attname: (
                    getattr(obj, f.attname).isoformat()
                    if hasattr(getattr(obj, f.attname), "isoformat")
                    else str(getattr(obj, f.attname))
                    if hasattr(getattr(obj, f.attname), "hex")
                    else getattr(obj, f.attname)
                )
                for f in obj._meta.concrete_fields
            }
    return out
