"""
Writes for study time: sessions (record, manual entry, edit, delete, undo, merge, split), the live stopwatch, goals and
settings. Everything is transactional and idempotent where a client can retry (`client_id`, optional `version`).

Server time is the clock. `_now()` is the single time source so tests can pin it.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Callable
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.db import IntegrityError, transaction
from django.db.models import Sum
from django.utils import timezone

from modules.coverage import selectors as coverage_selectors
from modules.coverage import services as coverage
from modules.syllabus import selectors as syllabus

from . import rollups, selectors
from .domain import durations
from .domain.durations import DurationError
from .errors import ConflictError, GoneError, InvalidInput, NotFoundError
from .models import (
    ActiveStopwatch,
    ActivityType,
    DailyRollup,
    Goal,
    HourBucket,
    SessionAudit,
    Source,
    StudySession,
    TrackerSettings,
)

logger = logging.getLogger(__name__)

COVERAGE_EVENT_NAMESPACE = uuid.UUID("6f1d3c52-8a0e-4c7b-9d52-3b6a1c0e7a11")
LIVE_KINDS = ("pomodoro", "stopwatch")


def _now() -> datetime:
    return timezone.now()


# --- One live timer of any kind ---------------------------------------------------------------------------------
_live_timer_providers: list[Callable[[uuid.UUID], str | None]] = []


def register_live_timer_provider(provider: Callable[[uuid.UUID], str | None]) -> None:
    """
    Other timers (the F-01.1 Pomodoro) register a function returning their kind (for example "pomodoro") while the student
    has one running. This keeps the dependency direction `focus -> tracking`: tracking never imports focus.
    """
    if provider not in _live_timer_providers:
        _live_timer_providers.append(provider)


def live_timer_kind(user_id) -> str:
    if ActiveStopwatch.objects.filter(pk=user_id).exists():
        return "stopwatch"
    for provider in _live_timer_providers:
        kind = provider(user_id)
        if kind:
            return kind
    return "none"


def assert_no_live_timer(user_id) -> None:
    kind = live_timer_kind(user_id)
    if kind != "none":
        raise ConflictError("Another timer is already running.", {"live": kind}, code="timer_already_active")


# --- Settings -------------------------------------------------------------------------------------------------
def get_or_create_settings(user_id) -> TrackerSettings:
    settings, _ = TrackerSettings.objects.get_or_create(pk=user_id)
    return settings


def get_timezone(user_id) -> str:
    return get_or_create_settings(user_id).tz


def _check_tz(name: str) -> str:
    try:
        ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError, OSError):
        raise InvalidInput("Unknown time zone.", {"tz": ["Use an IANA name such as Asia/Kolkata."]}) from None
    return name


@transaction.atomic
def update_settings(user_id, changes: dict) -> tuple[TrackerSettings, list[str]]:
    settings = get_or_create_settings(user_id)
    changed: list[str] = []
    if "idle_minutes" in changes:
        value = changes["idle_minutes"]
        if value != 0 and not durations.IDLE_MINUTES_MIN <= value <= durations.IDLE_MINUTES_MAX:
            raise InvalidInput("Invalid idle time.", {"idle_minutes": ["Use 0 (off) or 5 to 60 minutes."]})
    if "week_start" in changes and changes["week_start"] not in (0, 1):
        raise InvalidInput("Invalid week start.", {"week_start": ["Use 1 for Monday or 0 for Sunday."]})
    if "default_activity_type" in changes and changes["default_activity_type"] not in durations.ACTIVITY_TYPES:
        raise InvalidInput("Invalid activity.", {"default_activity_type": ["Unknown activity type."]})
    if "tz" in changes:
        _check_tz(changes["tz"])
    for field in ("idle_minutes", "week_start", "default_activity_type", "tz", "auto_capture_enabled"):
        if field in changes and getattr(settings, field) != changes[field]:
            setattr(settings, field, changes[field])
            changed.append(field)
    if changed:
        settings.save()
    return settings, changed


def reset_settings(user_id) -> TrackerSettings:
    TrackerSettings.objects.filter(pk=user_id).delete()
    return get_or_create_settings(user_id)


# --- Tags -----------------------------------------------------------------------------------------------------
def _resolve_tags(subject_id, chapter_id):
    """Subject and chapter must exist, and the chapter must belong to the subject. A chapter alone fills in its subject."""
    chapter = None
    if chapter_id:
        chapter = syllabus.get_chapter(chapter_id)
        if not chapter or not chapter.is_active:
            raise InvalidInput("Unknown chapter.", {"chapter_id": ["Chapter not found."]})
    subject = None
    if subject_id:
        subject = syllabus.get_subject(subject_id)
        if not subject:
            raise InvalidInput("Unknown subject.", {"subject_id": ["Subject not found."]})
    if chapter and subject and chapter.subject_id != subject.id:
        raise InvalidInput("That chapter is not in that subject.", {"chapter_id": ["Chapter is not in the subject."]})
    if chapter and not subject:
        subject = chapter.subject
    return subject, chapter


def _check_activity(activity_type: str) -> str:
    if activity_type not in durations.ACTIVITY_TYPES:
        raise InvalidInput("Unknown activity type.", {"activity_type": ["Unknown activity type."]})
    return activity_type


def _check_note(note: str) -> str:
    note = (note or "").strip()
    if len(note) > durations.NOTE_MAX_CHARS:
        raise InvalidInput("Note too long.", {"note": [f"At most {durations.NOTE_MAX_CHARS} characters."]})
    return note


# --- Sessions -------------------------------------------------------------------------------------------------
def _overlapping(user_id, started_at, ended_at, study_date: date, exclude_ids=()) -> list[StudySession]:
    window = [study_date - timedelta(days=1), study_date, study_date + timedelta(days=1)]
    qs = StudySession.objects.filter(
        user_id=user_id, study_date__in=window, started_at__lt=ended_at, ended_at__gt=started_at
    )
    return list(qs.exclude(pk__in=exclude_ids).order_by("started_at"))


def _forward_to_coverage(session: StudySession) -> None:
    """FR-16: finished time reaches the chapter's coverage record. Idempotent (a fixed id per session), never raises."""
    if not session.chapter_id:
        return
    try:
        with transaction.atomic():
            coverage.record_event(
                session.user_id,
                session.chapter_id,
                "study_time",
                value=session.focus_seconds,
                source="tracking",
                client_id=uuid.uuid5(COVERAGE_EVENT_NAMESPACE, str(session.id)),
                occurred_at=session.ended_at,
                source_ref=str(session.id),
                strict=False,  # not enrolled in this chapter's syllabus (older scheme): quietly skipped
            )
    except Exception:  # noqa: BLE001 - tracking must never fail because coverage did
        logger.warning("Could not forward study time of session %s to coverage", session.id, exc_info=True)


def reconcile_coverage(user_id, session_ids) -> None:
    """
    Brings the coverage ledger in line with the sessions as they are now (FR-16 corrections). For each id it compares
    the seconds already forwarded per chapter with the seconds the session should carry and appends the signed
    difference. A session that no longer exists should carry nothing; auto-captured time is never forwarded. Self-healing
    and never raises, so the tracker keeps working if coverage is unavailable.
    """
    ids = [str(i) for i in dict.fromkeys(session_ids)]
    if not ids:
        return
    try:
        sent = coverage_selectors.tracked_study_seconds(user_id, ids)
        wanted: dict[tuple[str, object], int] = {}
        for s in StudySession.objects.filter(user_id=user_id, pk__in=ids).exclude(source=Source.AUTO):
            if s.chapter_id:
                wanted[(str(s.id), s.chapter_id)] = s.focus_seconds
        for key in set(sent) | set(wanted):
            delta = wanted.get(key, 0) - sent.get(key, 0)
            if delta:
                with transaction.atomic():
                    coverage.adjust_study_time(user_id, key[1], delta, source_ref=key[0])
    except Exception:  # noqa: BLE001 - tracking must never fail because coverage did
        logger.warning("Could not reconcile coverage for sessions %s", ids, exc_info=True)


def _new_session(
    user_id, *, source, started_at, ended_at, focus_seconds, subject, chapter, activity_type, note, **extra
):
    tz = extra.pop("tz", None) or get_timezone(user_id)
    return StudySession(
        user_id=user_id,
        source=source,
        started_at=started_at,
        ended_at=ended_at,
        focus_seconds=focus_seconds,
        paused_total_seconds=extra.pop("paused_total_seconds", 0),
        subject=subject,
        chapter=chapter,
        activity_type=activity_type,
        note=note,
        tz=tz,
        study_date=durations.local_date(started_at, tz),
        **extra,
    )


@transaction.atomic
def record_session(
    user_id,
    *,
    source: str,
    started_at: datetime,
    ended_at: datetime,
    focus_seconds: int,
    subject_id=None,
    chapter_id=None,
    activity_type: str = ActivityType.OTHER,
    note: str = "",
    client_id=None,
    forward: bool = True,
    **extra,
) -> tuple[StudySession, bool]:
    """
    The one writer of finished sessions, used by the stopwatch, manual entry and (later) the Pomodoro and auto capture.
    Returns (session, created). A repeated `client_id` returns the existing row untouched.
    """
    if client_id:
        existing = StudySession.objects.filter(user_id=user_id, client_id=client_id).first()
        if existing:
            return existing, False
    started_at, ended_at = durations.whole_seconds(started_at), durations.whole_seconds(ended_at)
    if focus_seconds < durations.MIN_SESSION_SECONDS:
        raise InvalidInput("Sessions shorter than one minute are not saved.", code="too_short")
    if focus_seconds > durations.span_seconds(started_at, ended_at):
        raise InvalidInput("Counted time cannot be longer than the session.", code="focus_over_span")
    subject, chapter = _resolve_tags(subject_id, chapter_id)
    session = _new_session(
        user_id,
        source=source,
        started_at=started_at,
        ended_at=ended_at,
        focus_seconds=focus_seconds,
        subject=subject,
        chapter=chapter,
        activity_type=_check_activity(activity_type),
        note=_check_note(note),
        client_id=client_id,
        paused_total_seconds=extra.pop(
            "paused_total_seconds", durations.span_seconds(started_at, ended_at) - focus_seconds
        ),
        **extra,
    )
    others = _overlapping(user_id, started_at, ended_at, session.study_date)
    live = {Source.POMODORO, Source.STOPWATCH}
    if source in live and any(o.source in live for o in others):
        raise ConflictError(
            "That time overlaps another timer session.",
            {"conflicts": [str(o.id) for o in others if o.source in live]},
            code="overlap",
        )
    session.overlaps_other = bool(others)
    try:
        with transaction.atomic():
            session.save()
    except IntegrityError:
        existing = StudySession.objects.filter(user_id=user_id, client_id=client_id).first() if client_id else None
        if existing:
            return existing, False
        raise
    rollups.refresh_days(user_id, rollups.touched_days(session))
    if forward:
        _forward_to_coverage(session)
    return session, True


@transaction.atomic
def add_manual(
    user_id,
    *,
    client_id,
    started_at: datetime,
    ended_at: datetime | None = None,
    duration_seconds: int | None = None,
    subject_id=None,
    chapter_id=None,
    activity_type: str = ActivityType.OTHER,
    note: str = "",
    on_overlap: str | None = None,
    confirm_old: bool = False,
) -> tuple[StudySession, bool]:
    """Manual entry (FR-8 to FR-10). Overlaps are never silently resolved: the caller picks trim, keep or reject."""
    existing = StudySession.objects.filter(user_id=user_id, client_id=client_id).first() if client_id else None
    if existing:
        return existing, False
    started_at = durations.whole_seconds(started_at)
    if ended_at is None:
        if not duration_seconds:
            raise InvalidInput("Give an end time or a duration.", {"ended_at": ["Required."]})
        ended_at = started_at + timedelta(seconds=duration_seconds)
    ended_at = durations.whole_seconds(ended_at)
    try:
        needs_confirm = durations.validate_manual_window(started_at, ended_at, _now())
    except DurationError as e:
        raise InvalidInput(str(e), code=e.code) from None
    if needs_confirm and not confirm_old:
        raise InvalidInput(
            "This entry is more than 60 days old. Please confirm it is right.",
            {"confirm_old": ["Tick to confirm."]},
            code="confirmation_required",
        )
    tz = get_timezone(user_id)
    study_date = durations.local_date(started_at, tz)
    others = _overlapping(user_id, started_at, ended_at, study_date)
    trimmed_from = None
    if others:
        choice = on_overlap or "reject"
        if choice == "reject":
            raise ConflictError(
                "That time overlaps other study time.", {"conflicts": [str(o.id) for o in others]}, code="overlap"
            )
        if choice == "trim":
            busy = [(o.started_at, o.ended_at) for o in others]
            segment = durations.longest_segment(durations.free_segments((started_at, ended_at), busy))
            if segment is None:
                raise InvalidInput("Nothing is left of that entry after removing the overlap.", code="fully_overlapped")
            trimmed_from = (started_at, ended_at)
            started_at, ended_at = segment
        elif choice != "keep":
            raise InvalidInput("Unknown overlap choice.", {"on_overlap": ["Use trim, keep or reject."]})
    session, created = record_session(
        user_id,
        source=Source.MANUAL,
        started_at=started_at,
        ended_at=ended_at,
        focus_seconds=durations.span_seconds(started_at, ended_at),
        subject_id=subject_id,
        chapter_id=chapter_id,
        activity_type=activity_type,
        note=note,
        client_id=client_id,
    )
    if created and trimmed_from:
        _audit(
            user_id,
            SessionAudit.Action.MANUAL_TRIM,
            {"original_started_at": trimmed_from[0].isoformat(), "original_ended_at": trimmed_from[1].isoformat()},
            1,
            undoable=False,
        )
    return session, created


# --- Audit, undo ----------------------------------------------------------------------------------------------
_SNAPSHOT_FIELDS = [
    f.name
    for f in StudySession._meta.concrete_fields
    if f.name not in {"note", "created_at", "updated_at", "subject", "chapter", "split_from"}
] + ["subject_id", "chapter_id", "split_from_id"]


@transaction.atomic
def add_auto(user_id, *, client_id, chapter_id, started_at: datetime, seconds: int) -> tuple[StudySession | None, str]:
    """
    Opt-in auto capture (F-01.2 Q1): the web reports time spent actively on a syllabus chapter page. Returns
    (session, outcome) where outcome is "saved", "too_short", "timer_running", "overlap" or "daily_cap". Auto time never
    competes with a live timer or other recorded time, is capped per post and per day, and is not forwarded to coverage.
    """
    existing = selectors.session_by_client_id(user_id, client_id)
    if existing:
        return existing, "saved"
    if not get_or_create_settings(user_id).auto_capture_enabled:
        raise ConflictError("Auto capture is switched off.", code="auto_capture_off")
    if live_timer_kind(user_id) != "none":
        return None, "timer_running"
    now = _now()
    started = durations.whole_seconds(durations.clamp_client_time(started_at, now))
    ended = min(
        started + timedelta(seconds=min(seconds, durations.AUTO_MAX_CHUNK_SECONDS)), durations.whole_seconds(now)
    )
    focus = durations.span_seconds(started, ended)
    if focus < durations.MIN_SESSION_SECONDS:
        return None, "too_short"
    subject, chapter = _resolve_tags(None, chapter_id)
    study_date = durations.local_date(started, get_timezone(user_id))
    if _overlapping(user_id, started, ended, study_date):
        return None, "overlap"
    today_auto = (
        StudySession.objects.filter(user_id=user_id, study_date=study_date, source=Source.AUTO).aggregate(
            total=Sum("focus_seconds")
        )["total"]
        or 0
    )
    if today_auto + focus > durations.AUTO_DAILY_CAP_SECONDS:
        return None, "daily_cap"
    session, _ = record_session(
        user_id,
        source=Source.AUTO,
        started_at=started,
        ended_at=ended,
        focus_seconds=focus,
        subject_id=subject.id if subject else None,
        chapter_id=chapter.id,
        activity_type=ActivityType.READING,
        client_id=client_id,
        forward=False,
    )
    return session, "saved"


def _snapshot(session: StudySession) -> dict:
    data = {}
    for name in _SNAPSHOT_FIELDS:
        value = getattr(session, name)
        data[name] = (
            value.isoformat() if hasattr(value, "isoformat") else str(value) if isinstance(value, uuid.UUID) else value
        )
    return data


def _restore(user_id, data: dict, note: str = "") -> StudySession:
    values = dict(data)
    for name in ("started_at", "ended_at", "original_started_at", "original_ended_at"):
        if values.get(name):
            values[name] = datetime.fromisoformat(values[name])
    values["study_date"] = date.fromisoformat(values["study_date"])
    values["user_id"] = user_id
    values["note"] = _check_note(note)
    for name in ("id", "client_id", "cycle_id"):
        if values.get(name):
            values[name] = uuid.UUID(values[name])
    for name in ("subject_id", "chapter_id", "split_from_id"):
        if values.get(name):
            values[name] = uuid.UUID(values[name])
    # A tag that was removed since is quietly dropped rather than blocking the undo.
    return StudySession.objects.create(**values)


def _audit(user_id, action, snapshot, count, *, undoable=True) -> SessionAudit:
    now = _now()
    SessionAudit.objects.filter(user_id=user_id, created_at__lt=now - timedelta(days=30)).delete()
    return SessionAudit.objects.create(
        user_id=user_id,
        action=action,
        snapshot=snapshot,
        session_count=count,
        undo_until=now + timedelta(seconds=durations.UNDO_SECONDS if undoable else 0),
    )


def _own_session(user_id, session_id, *, lock=True) -> StudySession:
    qs = StudySession.objects.filter(user_id=user_id, pk=session_id)
    session = (qs.select_for_update() if lock else qs).first()
    if not session:
        raise NotFoundError("Session not found.")
    return session


@transaction.atomic
def delete_session(user_id, session_id) -> SessionAudit:
    session = _own_session(user_id, session_id)
    audit = _audit(user_id, SessionAudit.Action.DELETE, {"rows": [_snapshot(session)]}, 1)
    days = rollups.touched_days(session)
    session.delete()
    rollups.refresh_days(user_id, days)
    reconcile_coverage(user_id, [session_id])
    return audit


@transaction.atomic
def undo(user_id, token, notes: dict | None = None) -> list[StudySession]:
    audit = SessionAudit.objects.select_for_update().filter(user_id=user_id, pk=token).first()
    if not audit or audit.action not in {"delete", "merge", "split"}:
        raise NotFoundError("Nothing to undo.")
    if _now() > audit.undo_until:
        raise GoneError("Too late to undo.")
    notes = notes or {}
    days: set[date] = set()
    restored: list[StudySession] = []
    if audit.action == "merge":
        created = StudySession.objects.filter(user_id=user_id, pk=audit.snapshot["result_id"]).first()
        if created:
            days |= rollups.touched_days(created)
            created.delete()
    if audit.action == "split":
        part = StudySession.objects.filter(user_id=user_id, pk=audit.snapshot["part_id"]).first()
        if part:
            days |= rollups.touched_days(part)
            part.delete()
        StudySession.objects.filter(user_id=user_id, pk=audit.snapshot["rows"][0]["id"]).delete()
    for row in audit.snapshot["rows"]:
        session = _restore(user_id, row, notes.get(row["id"], ""))
        days |= rollups.touched_days(session)
        restored.append(session)
    audit.delete()
    rollups.refresh_days(user_id, days)
    reconcile_coverage(user_id, [str(r["id"]) for r in audit.snapshot["rows"]] + [str(s.id) for s in restored])
    if audit.action == "merge":
        reconcile_coverage(user_id, [audit.snapshot["result_id"]])
    if audit.action == "split":
        reconcile_coverage(user_id, [audit.snapshot["part_id"]])
    return restored


# --- Edit, merge, split -----------------------------------------------------------------------------------------
@transaction.atomic
def edit_session(user_id, session_id, changes: dict) -> StudySession:
    session = _own_session(user_id, session_id)
    before_days = rollups.touched_days(session)
    if "activity_type" in changes:
        session.activity_type = _check_activity(changes["activity_type"])
    if "note" in changes:
        session.note = _check_note(changes["note"])
    if "subject_id" in changes or "chapter_id" in changes:
        subject_id = changes.get("subject_id", session.subject_id)
        chapter_id = changes.get("chapter_id", session.chapter_id)
        if "subject_id" in changes and "chapter_id" not in changes and chapter_id:
            # Changing the subject drops a chapter that no longer fits.
            chapter = syllabus.get_chapter(chapter_id)
            if not chapter or chapter.subject_id != subject_id:
                chapter_id = None
        session.subject, session.chapter = _resolve_tags(subject_id, chapter_id)
    if "started_at" in changes or "ended_at" in changes:
        if session.source == Source.POMODORO:
            raise InvalidInput("Pomodoro rounds keep their times.", code="pomodoro_times_fixed")
        started = durations.whole_seconds(changes.get("started_at", session.started_at))
        ended = durations.whole_seconds(changes.get("ended_at", session.ended_at))
        try:
            needs_confirm = durations.validate_manual_window(started, ended, _now())
        except DurationError as e:
            raise InvalidInput(str(e), code=e.code) from None
        if needs_confirm and not changes.get("confirm_old") and started != session.started_at:
            raise InvalidInput(
                "This is more than 60 days ago. Please confirm.",
                {"confirm_old": ["Tick to confirm."]},
                code="confirmation_required",
            )
        span = durations.span_seconds(started, ended)
        if session.source != Source.MANUAL and span > durations.MAX_SESSION_SECONDS:
            raise InvalidInput("A timer session can be at most 12 hours.", code="too_long")
        if (started, ended) != (session.started_at, session.ended_at):
            _audit(
                user_id,
                SessionAudit.Action.EDIT_TIMES,
                {
                    "id": str(session.id),
                    "started_at": session.started_at.isoformat(),
                    "ended_at": session.ended_at.isoformat(),
                },
                1,
                undoable=False,
            )
            if session.original_started_at is None:
                session.original_started_at, session.original_ended_at = session.started_at, session.ended_at
            session.started_at, session.ended_at = started, ended
            session.focus_seconds, session.paused_total_seconds = span, 0  # the student states the real times
            session.tz = session.tz or get_timezone(user_id)
            session.study_date = durations.local_date(started, session.tz)
            session.is_edited = True
            session.edit_count += 1
            session.overlaps_other = bool(
                _overlapping(user_id, started, ended, session.study_date, exclude_ids=[session.id])
            )
    session.save()
    rollups.refresh_days(user_id, before_days | rollups.touched_days(session))
    reconcile_coverage(user_id, [session.id])
    return session


@transaction.atomic
def merge_sessions(user_id, session_ids: list, choice: dict) -> StudySession:
    """Merge adjacent same-day sessions (FR-13). Differing tags need an explicit pick in `choice`."""
    ids = list(dict.fromkeys(session_ids))
    sessions = list(StudySession.objects.select_for_update().filter(user_id=user_id, pk__in=ids))
    if len(sessions) != len(ids):
        raise NotFoundError("Session not found.")
    if len(sessions) < 2:
        raise InvalidInput("Pick at least two sessions to merge.", code="too_few")
    if len({s.study_date for s in sessions}) > 1:
        raise InvalidInput("Only sessions from the same day can be merged.", code="different_days")
    try:
        merged = durations.merge_pieces(
            [
                durations.Piece(s.started_at, s.ended_at, s.focus_seconds, s.paused_total_seconds, s.pause_count)
                for s in sessions
            ]
        )
    except DurationError as e:
        raise InvalidInput(str(e), code=e.code) from None
    tags = {(s.subject_id, s.chapter_id) for s in sessions}
    if "subject_id" in choice or "chapter_id" in choice:
        subject_id, chapter_id = choice.get("subject_id"), choice.get("chapter_id")
    elif len(tags) == 1:
        subject_id, chapter_id = next(iter(tags))
    else:
        raise InvalidInput(
            "These sessions have different subjects. Pick the one to keep.",
            {"subject_id": ["Pick a subject."]},
            code="choice_required",
        )
    subject, chapter = _resolve_tags(subject_id, chapter_id)
    ordered = sorted(sessions, key=lambda s: s.started_at)
    longest = max(sessions, key=lambda s: s.focus_seconds)
    all_stopwatch = all(s.source == Source.STOPWATCH for s in sessions)
    note = " / ".join(s.note for s in ordered if s.note)[: durations.NOTE_MAX_CHARS]
    days = set().union(*(rollups.touched_days(s) for s in sessions))
    audit = _audit(
        user_id, SessionAudit.Action.MERGE, {"rows": [_snapshot(s) for s in sessions], "result_id": ""}, len(sessions)
    )
    StudySession.objects.filter(pk__in=ids).delete()
    result = _new_session(
        user_id,
        source=Source.STOPWATCH if all_stopwatch else Source.MANUAL,
        started_at=merged.started_at,
        ended_at=merged.ended_at,
        focus_seconds=merged.focus_seconds,
        paused_total_seconds=merged.paused_total_seconds,
        pause_count=merged.pause_count,
        subject=subject,
        chapter=chapter,
        activity_type=choice.get("activity_type") or longest.activity_type,
        note=note,
        tz=ordered[0].tz,
        presence_verified=all(s.presence_verified for s in sessions),
        merged_count=sum(s.merged_count for s in sessions),
    )
    result.overlaps_other = bool(
        _overlapping(user_id, result.started_at, result.ended_at, result.study_date, exclude_ids=ids)
    )
    result.save()
    audit.snapshot = {**audit.snapshot, "result_id": str(result.id)}
    audit.save(update_fields=["snapshot"])
    rollups.refresh_days(user_id, days | rollups.touched_days(result))
    reconcile_coverage(user_id, ids + [result.id])
    return result


@transaction.atomic
def split_session(user_id, session_id, at: datetime) -> tuple[StudySession, StudySession, SessionAudit]:
    session = _own_session(user_id, session_id)
    if session.source == Source.POMODORO:
        raise InvalidInput("Pomodoro rounds cannot be split.", code="pomodoro_fixed")
    at = durations.whole_seconds(at)
    try:
        first, second = durations.split_piece(
            durations.Piece(
                session.started_at,
                session.ended_at,
                session.focus_seconds,
                session.paused_total_seconds,
                session.pause_count,
            ),
            at,
        )
    except DurationError as e:
        raise InvalidInput(str(e), code=e.code) from None
    days = rollups.touched_days(session)
    part = _new_session(
        user_id,
        source=session.source,
        started_at=second.started_at,
        ended_at=second.ended_at,
        focus_seconds=second.focus_seconds,
        subject=session.subject,
        chapter=session.chapter,
        activity_type=session.activity_type,
        note="",
        tz=session.tz,
        split_from=session,
        presence_verified=session.presence_verified,
        is_edited=True,
    )
    audit = _audit(user_id, SessionAudit.Action.SPLIT, {"rows": [_snapshot(session)], "part_id": str(part.id)}, 2)
    if session.original_started_at is None:
        session.original_started_at, session.original_ended_at = session.started_at, session.ended_at
    session.ended_at = first.ended_at
    session.focus_seconds, session.paused_total_seconds, session.pause_count = (
        first.focus_seconds,
        first.paused_total_seconds,
        first.pause_count,
    )
    session.is_edited, session.edit_count = True, session.edit_count + 1
    session.save()
    part.save()
    rollups.refresh_days(user_id, days | rollups.touched_days(session) | rollups.touched_days(part))
    reconcile_coverage(user_id, [session.id, part.id])
    return session, part, audit


# --- Stopwatch ------------------------------------------------------------------------------------------------
def _lock_stopwatch(user_id) -> ActiveStopwatch | None:
    return ActiveStopwatch.objects.select_for_update().filter(pk=user_id).first()


def _bump(sw: ActiveStopwatch, now: datetime, *, active: bool = True) -> None:
    sw.version += 1
    sw.last_seen_at = now
    if active:
        sw.last_active_at = now
    sw.save()


def _stale(sw: ActiveStopwatch, version, now) -> ConflictError:
    return ConflictError(
        "The stopwatch changed on another device.",
        {"stopwatch": selectors.stopwatch_dict(sw, now, get_or_create_settings(sw.user_id))},
        code="stale_version",
    )


def _resolve_idle(sw: ActiveStopwatch, now: datetime) -> None:
    """If the "Still studying?" prompt went unanswered for two minutes, pause at the last active moment (FR-7)."""
    if sw.idle_pending and not sw.paused_at and durations.idle_expired(now, sw.idle_prompted_at):
        sw.paused_at = min(now, max(sw.last_active_at, sw.started_at))
        sw.pause_count += 1
        sw.idle_pending, sw.idle_prompted_at = False, None
        sw.version += 1
        sw.save()


def _live_stopwatch(user_id, version, now) -> ActiveStopwatch:
    sw = _lock_stopwatch(user_id)
    if not sw:
        raise NotFoundError("No stopwatch is running.")
    _resolve_idle(sw, now)
    if version is not None and sw.version != version:
        raise _stale(sw, version, now)
    return sw


@transaction.atomic
def start_stopwatch(
    user_id, *, client_id, subject_id=None, chapter_id=None, activity_type=None, at: datetime | None = None
) -> tuple[ActiveStopwatch, bool]:
    now = _now()
    existing = _lock_stopwatch(user_id)
    if existing:
        if existing.client_id == client_id:
            return existing, False  # a retried Start
        raise ConflictError(
            "A stopwatch is already running.",
            {
                "live": "stopwatch",
                "stopwatch": selectors.stopwatch_dict(existing, now, get_or_create_settings(user_id)),
            },
            code="timer_already_active",
        )
    if StudySession.objects.filter(user_id=user_id, client_id=client_id).exists():
        raise ConflictError("That stopwatch has already finished.", code="client_id_used")
    assert_no_live_timer(user_id)
    subject, chapter = _resolve_tags(subject_id, chapter_id)
    settings = get_or_create_settings(user_id)
    started = durations.whole_seconds(durations.clamp_client_time(at, now))
    try:
        with transaction.atomic():
            sw = ActiveStopwatch.objects.create(
                user_id=user_id,
                started_at=started,
                last_seen_at=now,
                last_active_at=now,
                subject=subject,
                chapter=chapter,
                activity_type=_check_activity(activity_type or settings.default_activity_type),
                client_id=client_id,
            )
    except IntegrityError:
        raise ConflictError(
            "A stopwatch is already running.", {"live": "stopwatch"}, code="timer_already_active"
        ) from None
    return sw, True


@transaction.atomic
def pause_stopwatch(user_id, *, version=None, at: datetime | None = None) -> ActiveStopwatch:
    now = _now()
    sw = _live_stopwatch(user_id, version, now)
    if sw.paused_at:
        return sw  # already paused: a replayed Pause is harmless
    moment = durations.whole_seconds(durations.clamp_client_time(at, now))
    sw.paused_at = max(moment, sw.started_at)
    sw.pause_count += 1
    sw.idle_pending, sw.idle_prompted_at = False, None
    _bump(sw, now)
    return sw


@transaction.atomic
def resume_stopwatch(user_id, *, version=None, at: datetime | None = None) -> ActiveStopwatch:
    now = _now()
    sw = _live_stopwatch(user_id, version, now)
    if not sw.paused_at:
        return sw
    moment = durations.whole_seconds(durations.clamp_client_time(at, now))
    sw.paused_total_seconds += max(0, durations.span_seconds(sw.paused_at, max(moment, sw.paused_at)))
    sw.paused_at = None
    sw.idle_pending, sw.idle_prompted_at = False, None
    _bump(sw, now)
    return sw


@transaction.atomic
def change_stopwatch_context(user_id, *, version, changes: dict) -> ActiveStopwatch:
    now = _now()
    sw = _live_stopwatch(user_id, version, now)
    if "activity_type" in changes:
        sw.activity_type = _check_activity(changes["activity_type"])
    if "subject_id" in changes or "chapter_id" in changes:
        subject_id = changes.get("subject_id", sw.subject_id)
        chapter_id = changes.get("chapter_id", sw.chapter_id)
        if "subject_id" in changes and "chapter_id" not in changes and chapter_id:
            chapter = syllabus.get_chapter(chapter_id)
            if not chapter or chapter.subject_id != subject_id:
                chapter_id = None
        sw.subject, sw.chapter = _resolve_tags(subject_id, chapter_id)
    _bump(sw, now)
    return sw


@transaction.atomic
def answer_idle(user_id, *, answer: str) -> ActiveStopwatch:
    """The page tells us the "Still studying?" prompt was shown, or that the student said yes. Not a versioned change."""
    now = _now()
    sw = _live_stopwatch(user_id, None, now)
    if answer == "prompted":
        if not sw.paused_at and not sw.idle_pending:
            sw.idle_pending, sw.idle_prompted_at = True, now
    elif answer == "still_studying":
        sw.idle_pending, sw.idle_prompted_at, sw.last_active_at = False, None, now
    else:
        raise InvalidInput("Unknown answer.", {"answer": ["Use prompted or still_studying."]})
    sw.last_seen_at = now
    sw.save()
    return sw


@transaction.atomic
def sync_stopwatch(user_id, *, alive: bool = False, active: bool = False) -> ActiveStopwatch | None:
    """
    What a page loads or polls. Applies a lapsed idle prompt, and records a heartbeat (`alive`) and user activity
    (`active`) without changing `version`.
    """
    now = _now()
    sw = _lock_stopwatch(user_id)
    if not sw:
        return None
    _resolve_idle(sw, now)
    if alive or active:
        sw.last_seen_at = now
        if active:
            sw.last_active_at = now
        sw.save(update_fields=["last_seen_at", "last_active_at", "updated_at"])
    return sw


@transaction.atomic
def stop_stopwatch(
    user_id, *, client_id=None, version=None, save: bool = True, end_at: datetime | None = None
) -> tuple[StudySession | None, str]:
    """
    Stop and (by default) save. Returns (session, outcome) where outcome is "saved", "too_short" or "discarded".
    A repeated Stop (the stopwatch row is gone) returns the already saved session when `client_id` is given.
    """
    now = _now()
    sw = _lock_stopwatch(user_id)
    if not sw:
        existing = StudySession.objects.filter(user_id=user_id, client_id=client_id).first() if client_id else None
        if existing:
            return existing, "saved"
        raise NotFoundError("No stopwatch is running.")
    _resolve_idle(sw, now)
    if version is not None and sw.version != version:
        raise _stale(sw, version, now)
    outcome = durations.stop_outcome(
        sw.started_at,
        now,
        paused_at=sw.paused_at,
        paused_total=sw.paused_total_seconds,
        last_active_at=sw.last_active_at,
        requested_end=durations.clamp_client_time(end_at, now) if end_at else None,
    )
    fields = dict(
        subject_id=sw.subject_id,
        chapter_id=sw.chapter_id,
        activity_type=sw.activity_type,
        client_id=sw.client_id,
        started_at=sw.started_at,
        pause_count=sw.pause_count,
    )
    paused_total = durations.span_seconds(sw.started_at, outcome.ended_at) - outcome.focus_seconds
    sw.delete()
    if not save:
        return None, "discarded"
    if outcome.focus_seconds < durations.MIN_SESSION_SECONDS:
        return None, "too_short"
    session, _ = record_session(
        user_id,
        source=Source.STOPWATCH,
        ended_at=outcome.ended_at,
        focus_seconds=outcome.focus_seconds,
        paused_total_seconds=paused_total,
        idle_trimmed=outcome.idle_trimmed,
        **fields,
    )
    return session, "saved"


# --- Goals ----------------------------------------------------------------------------------------------------
def local_today(user_id) -> date:
    return durations.local_date(_now(), get_timezone(user_id))


@transaction.atomic
def set_goals(user_id, goals: list[dict]) -> list[Goal]:
    """
    Replace the student's goals (FR-17, FR-18, FR-20). Each entry is {period, subject_id|None, target_minutes}. A changed
    goal closes the old row the day before and opens a new one today, so earlier days keep the goal they had.
    """
    today = local_today(user_id)
    wanted: dict[tuple[str, str], tuple[dict, object]] = {}
    for entry in goals:
        period, minutes = entry["period"], entry["target_minutes"]
        low, high = (
            (durations.GOAL_DAILY_MIN, durations.GOAL_DAILY_MAX)
            if period == "daily"
            else (durations.GOAL_WEEKLY_MIN, durations.GOAL_WEEKLY_MAX)
        )
        if not low <= minutes <= high:
            raise InvalidInput(
                f"A {period} goal must be {low} to {high} minutes.", {"target_minutes": ["Out of range."]}
            )
        subject = None
        if entry.get("subject_id"):
            subject = syllabus.get_subject(entry["subject_id"])
            if not subject:
                raise InvalidInput("Unknown subject.", {"subject_id": ["Subject not found."]})
        key = (period, subject.key if subject else "")
        if key in wanted:
            raise InvalidInput("Each goal can be set once.", {"goals": [f"Duplicate {period} goal."]})
        wanted[key] = (entry, subject)
    open_goals = {
        (g.period, g.subject_key): g
        for g in Goal.objects.select_for_update().filter(user_id=user_id, effective_to__isnull=True)
    }
    for key, goal in open_goals.items():
        if key in wanted and wanted[key][0]["target_minutes"] == goal.target_minutes:
            continue
        if goal.effective_from >= today:
            goal.delete()  # changed on the day it began: nothing to preserve
        else:
            goal.effective_to = today - timedelta(days=1)
            goal.save(update_fields=["effective_to"])
    for key, (entry, subject) in wanted.items():
        current = open_goals.get(key)
        if current and current.target_minutes == entry["target_minutes"]:
            continue
        Goal.objects.create(
            user_id=user_id,
            period=key[0],
            subject=subject,
            subject_key=key[1],
            target_minutes=entry["target_minutes"],
            effective_from=today,
        )
    return list(selectors.goals_in_force(user_id, today))


# --- Data rights ----------------------------------------------------------------------------------------------
@transaction.atomic
def delete_all_for_user(user_id) -> dict:
    """Removes every tracking row of the student (PRD FR-34). Called by the account deletion flow."""
    summary = {"sessions": StudySession.objects.filter(user_id=user_id).count()}
    ActiveStopwatch.objects.filter(pk=user_id).delete()
    StudySession.objects.filter(user_id=user_id).delete()
    Goal.objects.filter(user_id=user_id).delete()
    TrackerSettings.objects.filter(pk=user_id).delete()
    SessionAudit.objects.filter(user_id=user_id).delete()
    DailyRollup.objects.filter(user_id=user_id).delete()
    HourBucket.objects.filter(user_id=user_id).delete()
    return summary
