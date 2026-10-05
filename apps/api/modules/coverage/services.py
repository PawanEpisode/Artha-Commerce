"""
Write operations for coverage. All transactional and idempotent.

`coverage.services.record_event` is the single entry point other modules (tracking, question bank, mocks, notes) use to
report progress. The ledger (`CoverageEvent`) is the source of truth; progress rows and roll-ups are derived and
`rebuild_enrollment` recomputes them from the ledger.
"""

from __future__ import annotations

import math
from collections import defaultdict
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

from django.db import IntegrityError, transaction
from django.utils import timezone

from modules.syllabus import matching
from modules.syllabus import selectors as syllabus
from modules.syllabus.models import Chapter, ChapterMap, Scheme, Topic

from . import selectors
from .domain import formula
from .errors import ConflictError, InvalidInput, NotFoundError
from .models import (
    DEFAULT_REVISION_DAYS,
    ChapterProgress,
    CoverageEvent,
    CoverageSettings,
    Enrollment,
    EnrollmentElective,
    Rollup,
    TopicProgress,
)

EventType = CoverageEvent.Type
Source = CoverageEvent.Source

CLIENT_EVENT_TYPES = {EventType.PRACTICE_DONE, EventType.MOCK_DONE, EventType.REVISION_DONE}
INTERNAL_EVENT_TYPES = CLIENT_EVENT_TYPES | {EventType.STUDY_TIME, EventType.NOTE_ADDED}
FUTURE_SKEW = timedelta(minutes=5)
BACKDATE_WINDOW = timedelta(days=7)


# --- settings --------------------------------------------------------------------------------


def get_or_create_settings(user_id) -> CoverageSettings:
    obj, _ = CoverageSettings.objects.get_or_create(
        user_id=user_id, defaults={"revision_days": list(DEFAULT_REVISION_DAYS)}
    )
    return obj


@transaction.atomic
def update_settings(
    user_id, *, weights: formula.Weights, revision_days: list[int], weighted_default: bool
) -> CoverageSettings:
    if not formula.weights_valid(weights):
        raise InvalidInput("Weights must be between 0 and 100 and total 100.", {"weights": ["Weights must total 100."]})
    if not formula.revision_days_valid(revision_days):
        raise InvalidInput(
            "Revision schedule is invalid.", {"revision_days": ["Use 1 to 8 gaps, each between 1 and 365 days."]}
        )
    settings = get_or_create_settings(user_id)
    settings.w_read, settings.w_practice = weights.read, weights.practice
    settings.w_revise, settings.w_mock = weights.revise, weights.mock
    settings.revision_days = revision_days
    settings.weighted_default = weighted_default
    settings.save()
    # Percentages recompute immediately; history (the ledger) is not rewritten.
    for enrollment in selectors.list_enrollments(user_id).filter(status=Enrollment.Status.ACTIVE):
        _recompute_enrollment(enrollment, settings)
    return settings


def reset_settings(user_id) -> CoverageSettings:
    return update_settings(
        user_id, weights=formula.Weights(), revision_days=list(DEFAULT_REVISION_DAYS), weighted_default=False
    )


# --- enrolment -------------------------------------------------------------------------------


@transaction.atomic
def create_enrollment(
    user_id,
    *,
    scheme_id,
    target_term_id=None,
    exam_date=None,
    daily_hours=None,
    carried_from: Enrollment | None = None,
    electives: dict[str, Any] | None = None,
) -> Enrollment:
    scheme = syllabus.get_scheme(scheme_id)
    if not scheme or scheme.status != Scheme.Status.PUBLISHED:
        raise NotFoundError("Scheme not found.")
    term = None
    if target_term_id:
        term = syllabus.list_terms(open_only=False).filter(pk=target_term_id, level=scheme.level).first()
        if not term:
            raise InvalidInput(
                "Exam term does not belong to this level.", {"target_term": ["Unknown term for this level."]}
            )
    if Enrollment.objects.filter(user_id=user_id, level=scheme.level, status=Enrollment.Status.ACTIVE).exists():
        raise ConflictError("You already have an active enrolment for this level.")
    # Progress is unique per (student, chapter), so enrolling again in a scheme you archived restores that enrolment
    # (with its progress) instead of starting a second copy.
    archived = Enrollment.objects.filter(user_id=user_id, scheme=scheme, status=Enrollment.Status.ARCHIVED).first()
    if archived:
        archived.status = Enrollment.Status.ACTIVE
        archived.target_term = term or archived.target_term
        archived.exam_date = exam_date or archived.exam_date
        archived.daily_hours = daily_hours or archived.daily_hours
        archived.save()
        if electives:
            _store_electives(archived, electives)
        _apply_electives(archived)
        _recompute_enrollment(archived, get_or_create_settings(user_id))
        return archived
    enrollment = Enrollment.objects.create(
        user_id=user_id,
        scheme=scheme,
        level=scheme.level,
        target_term=term,
        exam_date=exam_date,
        daily_hours=daily_hours,
        carried_from=carried_from,
    )
    settings = get_or_create_settings(user_id)
    ChapterProgress.objects.bulk_create(
        [
            ChapterProgress(user_id=user_id, enrollment=enrollment, chapter_id=chapter_id)
            for chapter_id in selectors.scheme_chapter_ids(scheme)
        ]
    )
    if electives:
        _store_electives(enrollment, electives)
    _apply_electives(enrollment)
    _recompute_enrollment(enrollment, settings)
    return enrollment


@transaction.atomic
def update_enrollment(enrollment: Enrollment, *, data: dict[str, Any]) -> Enrollment:
    """Change term, exam date or daily hours, or archive. A scheme change goes through `switch_scheme`."""
    if "target_term" in data:
        term = data["target_term"]
        if term and term.level_id != enrollment.scheme.level_id:
            raise InvalidInput(
                "Exam term does not belong to this level.", {"target_term": ["Unknown term for this level."]}
            )
        enrollment.target_term = term
    for field in ("exam_date", "daily_hours"):
        if field in data:
            setattr(enrollment, field, data[field])
    if data.get("archive"):
        enrollment.status = Enrollment.Status.ARCHIVED
    enrollment.save()
    return enrollment


# --- helpers ---------------------------------------------------------------------------------


def _clean_time(client_time: datetime | None) -> datetime:
    """Client time is accepted inside a window (not in the future, not older than 7 days); otherwise server time."""
    now = timezone.now()
    if client_time is None:
        return now
    if client_time.tzinfo is None:
        client_time = timezone.make_aware(client_time, timezone.utc)
    if client_time > now + FUTURE_SKEW or client_time < now - BACKDATE_WINDOW:
        return now
    return min(client_time, now)


def _enrollment_for_chapter(user_id, chapter: Chapter) -> Enrollment | None:
    return Enrollment.objects.filter(
        user_id=user_id, scheme_id=chapter.subject.scheme_id, status=Enrollment.Status.ACTIVE
    ).first()


def _progress_for(enrollment: Enrollment, chapter_id) -> ChapterProgress:
    progress, _ = ChapterProgress.objects.get_or_create(
        user_id=enrollment.user_id, chapter_id=chapter_id, defaults={"enrollment": enrollment}
    )
    return progress


def _append_event(
    enrollment: Enrollment,
    chapter_id,
    event_type: str,
    *,
    topic_id=None,
    value=None,
    payload: dict | None = None,
    source: str = Source.MANUAL,
    source_ref: str = "",
    client_id=None,
    occurred_at: datetime,
) -> tuple[CoverageEvent, bool]:
    """Idempotent on (user_id, client_id). Returns (event, created)."""
    if client_id:
        existing = CoverageEvent.objects.filter(user_id=enrollment.user_id, client_id=client_id).first()
        if existing:
            return existing, False
    try:
        with transaction.atomic():
            event = CoverageEvent.objects.create(
                user_id=enrollment.user_id,
                enrollment=enrollment,
                chapter_id=chapter_id,
                topic_id=topic_id,
                type=event_type,
                value=value,
                payload=payload or {},
                source=source,
                source_ref=source_ref,
                client_id=client_id,
                occurred_at=occurred_at,
            )
    except IntegrityError:  # a concurrent retry won the race
        return CoverageEvent.objects.get(user_id=enrollment.user_id, client_id=client_id), False
    return event, True


def apply_event(
    progress: ChapterProgress,
    event_type: str,
    *,
    value=None,
    payload: dict | None = None,
    occurred_at: datetime,
    revision_days: list[int],
) -> None:
    """Applies one ledger event to the derived counters of a chapter. Shared by the live path and the rebuild."""
    payload = payload or {}
    count = int(payload.get("count", 1))
    if progress.first_started_at is None or occurred_at < progress.first_started_at:
        progress.first_started_at = occurred_at
    if event_type in {
        EventType.TOPIC_DONE,
        EventType.PRACTICE_DONE,
        EventType.MOCK_DONE,
        EventType.REVISION_DONE,
        EventType.STUDY_TIME,
    }:
        if progress.last_studied_at is None or occurred_at > progress.last_studied_at:
            progress.last_studied_at = occurred_at

    if event_type == EventType.PRACTICE_DONE:
        progress.practice_count += count
    elif event_type == EventType.MOCK_DONE:
        progress.mock_count += count
    elif event_type == EventType.REVISION_DONE:
        progress.revision_count += count
        if progress.last_revised_at is None or occurred_at >= progress.last_revised_at:
            progress.last_revised_at = occurred_at
            progress.next_revision_due = formula.next_revision_due(
                occurred_at.date(), progress.revision_count, revision_days
            )
    elif event_type == EventType.STUDY_TIME:
        # A negative value is a correction from tracking (a session was edited or deleted); never below zero.
        progress.total_study_seconds = max(0, progress.total_study_seconds + int(value or 0))
    elif event_type == EventType.CONFIDENCE_SET:
        progress.confidence = payload.get("rating", "") or ""
    elif event_type == EventType.EXCLUDED:
        progress.is_excluded = True
    elif event_type == EventType.INCLUDED:
        progress.is_excluded = False


def _recompute_chapter(
    progress: ChapterProgress, chapter: Chapter, settings: CoverageSettings, counts: tuple[int, int]
) -> None:
    total, done = counts
    if total == 0:  # implicit single topic: the chapter itself
        total, done = 1, int(progress.implicit_topic_done)
    components = formula.compute_components(
        formula.ChapterInputs(
            topics_total=total,
            topics_done=done,
            practice_count=progress.practice_count,
            revision_count=progress.revision_count,
            mock_count=progress.mock_count,
            target_practice_sets=chapter.target_practice_sets,
            target_revisions=chapter.target_revisions,
            target_mocks=chapter.target_mocks,
        ),
        selectors.weights_of(settings),
    )
    progress.read_pct = components.read
    progress.practice_pct = components.practice
    progress.revise_pct = components.revise
    progress.mock_pct = components.mock
    progress.coverage_pct = components.coverage
    progress.status = formula.derive_status(
        read_pct=components.read,
        coverage_pct=components.coverage,
        practice_count=progress.practice_count,
        revision_count=progress.revision_count,
        any_activity=progress.first_started_at is not None,
    )


def _save_progress(progress: ChapterProgress) -> None:
    progress.save()


def _recompute_enrollment(enrollment: Enrollment, settings: CoverageSettings | None = None) -> None:
    """Recomputes every chapter of an enrolment and its roll-ups (used after settings change and on rebuild)."""
    settings = settings or get_or_create_settings(enrollment.user_id)
    rows = list(selectors.chapter_progress_for_enrollment(enrollment))
    counts = selectors.topic_counts(enrollment.user_id, [p.chapter_id for p in rows])
    for progress in rows:
        _recompute_chapter(progress, progress.chapter, settings, counts[progress.chapter_id])
    ChapterProgress.objects.bulk_update(
        rows,
        [
            "status",
            "read_pct",
            "practice_pct",
            "revise_pct",
            "mock_pct",
            "coverage_pct",
            "practice_count",
            "mock_count",
            "revision_count",
            "total_study_seconds",
            "first_started_at",
            "last_studied_at",
            "last_revised_at",
            "next_revision_due",
            "confidence",
            "is_excluded",
            "implicit_topic_done",
            "updated_at",
        ],
    )
    recompute_rollups(enrollment, rows)


def recompute_rollups(enrollment: Enrollment, rows: list[ChapterProgress] | None = None) -> None:
    """Subject, group and level roll-ups for an enrolment. At most a few dozen rows, replaced in one transaction."""
    rows = rows if rows is not None else list(selectors.chapter_progress_for_enrollment(enrollment))
    subject_group = dict(enrollment.scheme.subjects.filter(is_active=True).values_list("id", "group_id"))
    by_subject: dict = defaultdict(list)
    by_group: dict = defaultdict(list)
    everything: list[formula.RollupRow] = []
    for p in rows:
        row = formula.RollupRow(p.coverage_pct, p.chapter.marks_weight, p.is_excluded, p.status)
        by_subject[p.chapter.subject_id].append(row)
        group_id = subject_group.get(p.chapter.subject_id)
        if group_id:
            by_group[group_id].append(row)
        everything.append(row)

    now = timezone.now()
    out: list[Rollup] = []

    def add(node_type: str, node_id, items: list[formula.RollupRow]) -> None:
        r = formula.rollup(items)
        out.append(
            Rollup(
                enrollment=enrollment,
                node_type=node_type,
                node_id=node_id,
                pct_simple=r.pct_simple,
                pct_weighted=r.pct_weighted,
                chapters_total=r.chapters_total,
                chapters_done=r.chapters_done,
                updated_at=now,
            )
        )

    for subject_id, items in by_subject.items():
        add(Rollup.NodeType.SUBJECT, subject_id, items)
    for group_id, items in by_group.items():
        add(Rollup.NodeType.GROUP, group_id, items)
    add(Rollup.NodeType.LEVEL, enrollment.scheme.level_id, everything)

    Rollup.objects.filter(enrollment=enrollment).delete()
    Rollup.objects.bulk_create(out)


def _settle(enrollment: Enrollment, progresses: list[ChapterProgress]) -> None:
    """After a change: recompute the touched chapters and the roll-ups."""
    settings = get_or_create_settings(enrollment.user_id)
    counts = selectors.topic_counts(enrollment.user_id, [p.chapter_id for p in progresses])
    for progress in progresses:
        _recompute_chapter(progress, progress.chapter, settings, counts[progress.chapter_id])
        progress.save()
    recompute_rollups(enrollment)


# --- topics and catch-up ---------------------------------------------------------------------


@transaction.atomic
def adjust_study_time(
    user_id, chapter_id, delta_seconds: int, *, source_ref: str, source: str = Source.TRACKING
) -> None:
    """
    Signed correction to a chapter's study time, appended to the ledger (never edits history). Used by tracking when a
    session that was already forwarded is edited, deleted, merged, split or restored. Quietly skipped when the student
    is not enrolled in the chapter's syllabus. Callers pass the net difference, so a repeated call with 0 is a no-op.
    """
    delta = int(delta_seconds)
    if delta == 0:
        return
    chapter = syllabus.get_chapter(chapter_id)
    enrollment = _enrollment_for_chapter(user_id, chapter) if chapter else None
    if not chapter or not enrollment:
        return
    when = timezone.now()
    event, created = _append_event(
        enrollment,
        chapter.id,
        EventType.STUDY_TIME,
        value=delta,
        payload={"correction": True},
        source=source,
        source_ref=source_ref,
        occurred_at=when,
    )
    if not created:
        return
    progress = _progress_for(enrollment, chapter.id)
    apply_event(
        progress,
        EventType.STUDY_TIME,
        value=delta,
        occurred_at=when,
        revision_days=selectors.revision_days_of(get_or_create_settings(user_id)),
    )
    _settle(enrollment, [progress])


@transaction.atomic
def tick_topic(
    user_id, topic_id, *, done: bool, client_id=None, occurred_at: datetime | None = None
) -> ChapterProgress:
    topic = syllabus.get_topic(topic_id)
    if not topic:
        raise NotFoundError("Topic not found.")
    chapter = topic.chapter
    enrollment = _enrollment_for_chapter(user_id, chapter)
    if not enrollment:
        raise NotFoundError("You are not enrolled in the syllabus this topic belongs to.")
    progress = _progress_for(enrollment, chapter.id)
    when = _clean_time(occurred_at)
    event, created = _append_event(
        enrollment,
        chapter.id,
        EventType.TOPIC_DONE if done else EventType.TOPIC_UNDONE,
        topic_id=topic.id,
        client_id=client_id,
        occurred_at=when,
    )
    if not created:
        return progress
    existing = TopicProgress.objects.filter(user_id=user_id, topic_id=topic.id).first()
    if existing is None:
        TopicProgress.objects.create(
            user_id=user_id,
            topic_id=topic.id,
            enrollment=enrollment,
            is_done=done,
            done_at=when if done else None,
            updated_at=when,
        )
    elif existing.updated_at <= when:  # last write wins between devices; the ledger keeps both events
        TopicProgress.objects.filter(user_id=user_id, topic_id=topic.id).update(
            is_done=done, done_at=when if done else None, updated_at=when, enrollment=enrollment
        )
    apply_event(
        progress,
        event.type,
        occurred_at=when,
        revision_days=selectors.revision_days_of(get_or_create_settings(user_id)),
    )
    _settle(enrollment, [progress])
    return progress


@transaction.atomic
def tick_chapter(
    user_id, chapter_id, *, done: bool, client_id=None, occurred_at: datetime | None = None
) -> ChapterProgress:
    """For chapters without topics: the chapter itself is one implicit topic."""
    chapter = syllabus.get_chapter(chapter_id)
    if not chapter:
        raise NotFoundError("Chapter not found.")
    if chapter.topics.filter(is_active=True).exists():
        raise InvalidInput("This chapter has topics. Tick its topics instead.", {"chapter": ["Chapter has topics."]})
    enrollment = _enrollment_for_chapter(user_id, chapter)
    if not enrollment:
        raise NotFoundError("You are not enrolled in the syllabus this chapter belongs to.")
    progress = _progress_for(enrollment, chapter.id)
    when = _clean_time(occurred_at)
    event, created = _append_event(
        enrollment,
        chapter.id,
        EventType.TOPIC_DONE if done else EventType.TOPIC_UNDONE,
        payload={"implicit": True},
        client_id=client_id,
        occurred_at=when,
    )
    if not created:
        return progress
    progress.implicit_topic_done = done
    apply_event(
        progress,
        event.type,
        occurred_at=when,
        revision_days=selectors.revision_days_of(get_or_create_settings(user_id)),
    )
    _settle(enrollment, [progress])
    return progress


@transaction.atomic
def catchup(user_id, chapter_ids: list, *, also_revised: bool = False, client_id=None) -> dict:
    """Quick catch-up: mark whole chapters as read (and optionally revised once). One event per chapter."""
    enrollment = selectors.get_active_enrollment(user_id)
    if not enrollment:
        raise NotFoundError("Create an enrolment first.")
    if client_id and CoverageEvent.objects.filter(user_id=user_id, client_id=client_id).exists():
        return {"updated": 0, "duplicate": True}
    chapters = list(Chapter.objects.filter(pk__in=chapter_ids, subject__scheme=enrollment.scheme, is_active=True))
    if len(chapters) != len(set(chapter_ids)):
        raise InvalidInput("Some chapters are not part of your syllabus.", {"chapter_ids": ["Unknown chapter."]})
    settings = get_or_create_settings(user_id)
    revision_days = selectors.revision_days_of(settings)
    when = timezone.now()
    progresses = []
    for index, chapter in enumerate(chapters):
        progress = _progress_for(enrollment, chapter.id)
        topic_ids = list(chapter.topics.filter(is_active=True).values_list("id", flat=True))
        if topic_ids:
            _mark_topics_done(user_id, enrollment, topic_ids, when, Source.CATCHUP)
        else:
            progress.implicit_topic_done = True
        _, created = _append_event(
            enrollment,
            chapter.id,
            EventType.TOPIC_DONE,
            payload={"all": True},
            source=Source.CATCHUP,
            client_id=client_id if index == 0 else None,
            occurred_at=when,
        )
        if created:
            apply_event(progress, EventType.TOPIC_DONE, occurred_at=when, revision_days=revision_days)
        if also_revised and progress.revision_count == 0:
            _append_event(
                enrollment,
                chapter.id,
                EventType.REVISION_DONE,
                payload={"count": 1},
                source=Source.CATCHUP,
                occurred_at=when,
            )
            apply_event(
                progress, EventType.REVISION_DONE, payload={"count": 1}, occurred_at=when, revision_days=revision_days
            )
        progresses.append(progress)
    _settle(enrollment, progresses)
    return {"updated": len(progresses), "duplicate": False}


def _mark_topics_done(user_id, enrollment: Enrollment, topic_ids: list, when: datetime, source: str) -> None:
    existing = set(
        TopicProgress.objects.filter(user_id=user_id, topic_id__in=topic_ids).values_list("topic_id", flat=True)
    )
    TopicProgress.objects.filter(user_id=user_id, topic_id__in=list(existing)).update(
        is_done=True, done_at=when, updated_at=when, source=source, enrollment=enrollment
    )
    TopicProgress.objects.bulk_create(
        [
            TopicProgress(
                user_id=user_id,
                topic_id=t,
                enrollment=enrollment,
                is_done=True,
                done_at=when,
                source=source,
                updated_at=when,
            )
            for t in topic_ids
            if t not in existing
        ]
    )


# --- the ledger entry point ------------------------------------------------------------------


@transaction.atomic
def record_event(
    user_id,
    chapter_id,
    type: str,  # noqa: A002 (part of the documented internal interface)
    value=None,
    source: str = Source.MANUAL,
    client_id=None,
    *,
    occurred_at: datetime | None = None,
    payload: dict | None = None,
    source_ref: str = "",
    strict: bool = True,
) -> CoverageEvent | None:
    """
    Single entry point for other modules: `coverage.services.record_event(user_id, chapter_id, type, value, source, client_id)`.
    Idempotent on `client_id`. With `strict=False` it returns None instead of raising when the student is not enrolled in
    the chapter's syllabus (for example time tracked against an old scheme).
    """
    if type not in INTERNAL_EVENT_TYPES:
        raise InvalidInput(
            "Unsupported event type.", {"type": [f"Use one of: {', '.join(sorted(INTERNAL_EVENT_TYPES))}."]}
        )
    if type == EventType.STUDY_TIME and (value is None or Decimal(str(value)) <= 0):
        raise InvalidInput("Study time needs a positive value in seconds.", {"value": ["Must be greater than 0."]})
    chapter = syllabus.get_chapter(chapter_id)
    enrollment = _enrollment_for_chapter(user_id, chapter) if chapter else None
    if not chapter or not enrollment:
        if strict:
            raise NotFoundError("Chapter not found in your syllabus.")
        return None
    when = _clean_time(occurred_at)
    event, created = _append_event(
        enrollment,
        chapter.id,
        type,
        value=value,
        payload=payload,
        source=source,
        source_ref=source_ref,
        client_id=client_id,
        occurred_at=when,
    )
    if not created:
        return event
    progress = _progress_for(enrollment, chapter.id)
    apply_event(
        progress,
        type,
        value=value,
        payload=payload,
        occurred_at=when,
        revision_days=selectors.revision_days_of(get_or_create_settings(user_id)),
    )
    _settle(enrollment, [progress])
    return event


@transaction.atomic
def set_confidence(user_id, chapter_id, rating: str | None) -> ChapterProgress:
    if rating not in {None, "", "red", "amber", "green"}:
        raise InvalidInput("Confidence must be red, amber or green.", {"confidence": ["Invalid rating."]})
    chapter = syllabus.get_chapter(chapter_id)
    enrollment = _enrollment_for_chapter(user_id, chapter) if chapter else None
    if not chapter or not enrollment:
        raise NotFoundError("Chapter not found in your syllabus.")
    progress = _progress_for(enrollment, chapter.id)
    when = timezone.now()
    _append_event(enrollment, chapter.id, EventType.CONFIDENCE_SET, payload={"rating": rating or ""}, occurred_at=when)
    apply_event(
        progress, EventType.CONFIDENCE_SET, payload={"rating": rating or ""}, occurred_at=when, revision_days=[]
    )
    _settle(enrollment, [progress])
    return progress


@transaction.atomic
def set_exclusion(user_id, chapter_id, excluded: bool) -> ChapterProgress:
    chapter = syllabus.get_chapter(chapter_id)
    enrollment = _enrollment_for_chapter(user_id, chapter) if chapter else None
    if not chapter or not enrollment:
        raise NotFoundError("Chapter not found in your syllabus.")
    if not excluded:
        slot = _elective_slot_of(enrollment.scheme, chapter.subject_id)
        if slot and elective_choices(enrollment).get(slot.key) != chapter.subject_id:
            raise InvalidInput(
                "This chapter belongs to an elective you did not choose.",
                {"chapter": ["Choose this elective to count its chapters."]},
            )
    progress = _progress_for(enrollment, chapter.id)
    if progress.is_excluded != excluded:
        when = timezone.now()
        event_type = EventType.EXCLUDED if excluded else EventType.INCLUDED
        _append_event(enrollment, chapter.id, event_type, occurred_at=when)
        apply_event(progress, event_type, occurred_at=when, revision_days=[])
    _settle(enrollment, [progress])
    return progress


def _set_subject_excluded(
    enrollment: Enrollment, subject, excluded: bool, *, source: str = Source.MANUAL, when: datetime | None = None
) -> list[ChapterProgress]:
    """Writes EXCLUDED/INCLUDED events for every chapter of a subject that is not already in that state."""
    when = when or timezone.now()
    changed: list[ChapterProgress] = []
    for chapter in subject.chapters.filter(is_active=True):
        progress = _progress_for(enrollment, chapter.id)
        if progress.is_excluded != excluded:
            event_type = EventType.EXCLUDED if excluded else EventType.INCLUDED
            _append_event(enrollment, chapter.id, event_type, source=source, occurred_at=when)
            apply_event(progress, event_type, occurred_at=when, revision_days=[])
            changed.append(progress)
    return changed


@transaction.atomic
def set_subject_exclusion(user_id, subject_id, excluded: bool) -> int:
    subject = syllabus.get_published_subject(subject_id) or _retired_subject(subject_id)
    if not subject:
        raise NotFoundError("Subject not found.")
    enrollment = Enrollment.objects.filter(user_id=user_id, scheme_id=subject.scheme_id, status="active").first()
    if not enrollment:
        raise NotFoundError("You are not enrolled in the syllabus this subject belongs to.")
    if _elective_slot_of(enrollment.scheme, subject.id):
        raise InvalidInput(
            "This paper is an elective. Choose your elective instead of excluding papers.",
            {"subject": ["Elective papers are controlled by your elective choice."]},
        )
    changed = _set_subject_excluded(enrollment, subject, excluded)
    if changed:
        _settle(enrollment, changed)
    return len(changed)


# --- electives -------------------------------------------------------------------------------


def _elective_slot_of(scheme: Scheme, subject_id):
    return next(
        (slot for slot in syllabus.elective_slots(scheme) if any(o.id == subject_id for o in slot.options)), None
    )


def elective_choices(enrollment: Enrollment) -> dict[str, Any]:
    """slot key -> chosen subject id."""
    return {e.slot_key: e.subject_id for e in EnrollmentElective.objects.filter(enrollment=enrollment)}


def _store_electives(enrollment: Enrollment, choices: dict[str, Any]) -> None:
    """Validates and saves choices (a slot mapped to None clears it). Does not touch coverage; see `_apply_electives`."""
    slots = {s.key: s for s in syllabus.elective_slots(enrollment.scheme)}
    errors: dict[str, list[str]] = {}
    clean: dict[str, Any] = {}
    for key, subject_id in choices.items():
        slot = slots.get(key)
        if slot is None:
            errors[key] = ["Unknown elective slot for this syllabus."]
        elif subject_id is None:
            clean[key] = None
        elif not any(str(o.id) == str(subject_id) for o in slot.options):
            errors[key] = ["Not one of the options for this elective paper."]
        else:
            clean[key] = subject_id
    if errors:
        raise InvalidInput("Invalid elective choice.", {"electives": errors})
    for key, subject_id in clean.items():
        if subject_id is None:
            EnrollmentElective.objects.filter(enrollment=enrollment, slot_key=key).delete()
        else:
            EnrollmentElective.objects.update_or_create(
                enrollment=enrollment,
                slot_key=key,
                defaults={"user_id": enrollment.user_id, "subject_id": subject_id},
            )


def _apply_electives(enrollment: Enrollment) -> list[ChapterProgress]:
    """
    Makes coverage follow the choices: in every slot the chosen option counts and the others are excluded.
    A slot without a choice yet excludes all its options, so no paper is counted until the student picks one.
    """
    chosen = elective_choices(enrollment)
    when = timezone.now()
    changed: list[ChapterProgress] = []
    for slot in syllabus.elective_slots(enrollment.scheme):
        for option in slot.options:
            changed += _set_subject_excluded(
                enrollment, option, option.id != chosen.get(slot.key), source=Source.SYSTEM, when=when
            )
    for progress in changed:
        progress.save()  # callers recompute from the database
    return changed


@transaction.atomic
def sync_electives(enrollment: Enrollment) -> None:
    """
    Brings an enrolment in line with its elective choices. New enrolments are already in line; this catches students
    who enrolled before electives existed (their option papers were all counted) and slots a scheme gained later.
    A no-op when nothing differs.
    """
    if enrollment.status != Enrollment.Status.ACTIVE:
        return
    changed = _apply_electives(enrollment)
    if changed:
        _settle(enrollment, changed)


@transaction.atomic
def set_electives(enrollment: Enrollment, choices: dict[str, Any]) -> Enrollment:
    """Saves the student's elective choices for their active syllabus and re-counts coverage."""
    if enrollment.status != Enrollment.Status.ACTIVE:
        raise InvalidInput("Only an active enrolment can change electives.", {"enrollment": ["Not active."]})
    _store_electives(enrollment, choices)
    changed = _apply_electives(enrollment)
    if changed:
        _settle(enrollment, changed)
    return enrollment


def _retired_subject(subject_id):
    from modules.syllabus.models import Subject

    return Subject.objects.filter(pk=subject_id, scheme__status=Scheme.Status.RETIRED).first()


def _match_topics(old_done: list[tuple[str, str]], targets: list[Topic]) -> list[Topic]:
    """
    Topics of the new chapter that the student finished in the old one: same key first, then same normalised name
    (so a re-keyed or renumbered topic still carries over). Each target topic is used once, in the old order.
    """
    by_key = {t.key: t for t in targets}
    by_name: dict[str, Topic] = {}
    for t in targets:
        by_name.setdefault(matching.normalise(t.name), t)
    taken: set = set()
    matched: list[Topic] = []
    for key, name in old_done:
        topic = by_key.get(key) or by_name.get(matching.normalise(name))
        if topic is not None and topic.id not in taken:
            taken.add(topic.id)
            matched.append(topic)
    return matched


def _chapter_ref(chapter: Chapter) -> dict:
    return {
        "id": str(chapter.id),
        "key": chapter.key,
        "name": chapter.name,
        "subject": {"id": str(chapter.subject_id), "key": chapter.subject.key, "name": chapter.subject.name},
    }


# --- scheme switch with carry-over -----------------------------------------------------------


@transaction.atomic
def switch_scheme(user_id, enrollment: Enrollment, new_scheme_id, *, target_term_id=None) -> tuple[Enrollment, dict]:
    """Archives the old enrolment, creates one on the new scheme and carries progress through the chapter map (FR-28)."""
    new_scheme = syllabus.get_scheme(new_scheme_id)
    if not new_scheme or new_scheme.status != Scheme.Status.PUBLISHED:
        raise NotFoundError("Scheme not found.")
    if new_scheme.level_id != enrollment.level_id:
        raise InvalidInput("The new scheme must belong to the same level.", {"scheme": ["Different level."]})
    if new_scheme.id == enrollment.scheme_id:
        raise InvalidInput("You are already on this scheme.", {"scheme": ["Same scheme."]})

    old_rows = {p.chapter_id: p for p in selectors.chapter_progress_for_enrollment(enrollment)}
    old_choices = {e.slot_key: e.subject.key for e in enrollment.electives.select_related("subject")}
    enrollment.status = Enrollment.Status.ARCHIVED
    enrollment.save(update_fields=["status", "updated_at"])
    new = create_enrollment(
        user_id,
        scheme_id=new_scheme.id,
        target_term_id=target_term_id or enrollment.target_term_id,
        exam_date=enrollment.exam_date,
        daily_hours=enrollment.daily_hours,
        carried_from=enrollment,
    )

    maps = defaultdict(list)
    for m in ChapterMap.objects.filter(
        from_chapter_id__in=list(old_rows), to_chapter__subject__scheme=new_scheme
    ).select_related("to_chapter"):
        maps[m.to_chapter_id].append(m)

    settings = get_or_create_settings(user_id)
    revision_days = selectors.revision_days_of(settings)
    new_progress = {p.chapter_id: p for p in selectors.chapter_progress_for_enrollment(new)}
    new_chapters = {
        c.id: c for c in Chapter.objects.filter(subject__scheme=new_scheme, is_active=True).select_related("subject")
    }
    carried_ids: list = []
    touched: list[ChapterProgress] = []

    for chapter_id, incoming in maps.items():
        target = new_progress.get(chapter_id)
        if target is None:
            continue
        target_topics = list(new_chapters[chapter_id].topics.filter(is_active=True).order_by("sort_order", "key"))
        carried_topics: dict = {}
        counts = {"practice": 0, "mock": 0, "revision": 0}
        study_seconds = 0
        last_revised = None
        implicit = False
        confidence = ""
        all_excluded = True
        for m in incoming:
            src = old_rows[m.from_chapter_id]
            ratio = float(m.carry_ratio)
            all_excluded = all_excluded and src.is_excluded
            confidence = confidence or src.confidence
            old_done = list(
                TopicProgress.objects.filter(user_id=user_id, topic__chapter_id=m.from_chapter_id, is_done=True)
                .select_related("topic")
                .order_by("topic__sort_order", "topic__key")
                .values_list("topic__key", "topic__name")
            )
            matched = _match_topics(old_done, target_topics)
            # Topics are matched by name, so the ratio only trims them for an editor's explicit "partial" row.
            topic_ratio = ratio if m.relation == ChapterMap.Relation.PARTIAL else 1.0
            for topic in matched[: math.floor(len(matched) * topic_ratio + 0.5)]:
                carried_topics[topic.id] = topic
            implicit = implicit or (src.implicit_topic_done and not target_topics)
            counts["practice"] += math.floor(src.practice_count * ratio)
            counts["mock"] += math.floor(src.mock_count * ratio)
            counts["revision"] += math.floor(src.revision_count * ratio)
            study_seconds += math.floor(src.total_study_seconds * ratio)
            if src.last_revised_at and (last_revised is None or src.last_revised_at > last_revised):
                last_revised = src.last_revised_at
        now = timezone.now()
        wrote = False
        for topic in carried_topics.values():
            _mark_topics_done(user_id, new, [topic.id], now, Source.CARRYOVER)
            _append_event(
                new, chapter_id, EventType.TOPIC_DONE, topic_id=topic.id, source=Source.CARRYOVER, occurred_at=now
            )
            apply_event(target, EventType.TOPIC_DONE, occurred_at=now, revision_days=revision_days)
            wrote = True
        if implicit:
            target.implicit_topic_done = True
            _append_event(
                new,
                chapter_id,
                EventType.TOPIC_DONE,
                payload={"implicit": True},
                source=Source.CARRYOVER,
                occurred_at=now,
            )
            apply_event(target, EventType.TOPIC_DONE, occurred_at=now, revision_days=revision_days)
            wrote = True
        for kind, event_type in (
            ("practice", EventType.PRACTICE_DONE),
            ("mock", EventType.MOCK_DONE),
            ("revision", EventType.REVISION_DONE),
        ):
            if counts[kind] > 0:
                at = last_revised if (kind == "revision" and last_revised) else now
                _append_event(
                    new,
                    chapter_id,
                    event_type,
                    payload={"count": counts[kind]},
                    source=Source.CARRYOVER,
                    occurred_at=at,
                )
                apply_event(
                    target, event_type, payload={"count": counts[kind]}, occurred_at=at, revision_days=revision_days
                )
                wrote = True
        if study_seconds > 0:
            _append_event(
                new, chapter_id, EventType.STUDY_TIME, value=study_seconds, source=Source.CARRYOVER, occurred_at=now
            )
            apply_event(target, EventType.STUDY_TIME, value=study_seconds, occurred_at=now, revision_days=revision_days)
            wrote = True
        if confidence:
            _append_event(
                new,
                chapter_id,
                EventType.CONFIDENCE_SET,
                payload={"rating": confidence},
                source=Source.CARRYOVER,
                occurred_at=now,
            )
            apply_event(
                target, EventType.CONFIDENCE_SET, payload={"rating": confidence}, occurred_at=now, revision_days=[]
            )
        if all_excluded and incoming and not target.is_excluded:
            _append_event(new, chapter_id, EventType.EXCLUDED, source=Source.CARRYOVER, occurred_at=now)
            apply_event(target, EventType.EXCLUDED, occurred_at=now, revision_days=[])
        carried_ids.append(chapter_id)
        touched.append(target)
        _ = wrote

    if touched:
        _settle(new, touched)
    # Keep the student's elective choices: slots are matched by subject key, so a re-numbered scheme still lines up.
    carried_choices = {
        slot.key: option.id
        for slot in syllabus.elective_slots(new_scheme)
        for option in slot.options
        if old_choices.get(slot.key) == option.key
    }
    if carried_choices:
        set_electives(new, carried_choices)
    return new, _switch_summary(new_progress, new_chapters, old_rows, maps, carried_ids)


def _switch_summary(new_progress: dict, new_chapters: dict, old_rows: dict, maps: dict, carried_ids: list) -> dict:
    """The lists behind the switch screen: chapters that carried, chapters new to the student, chapters that are gone."""
    mapped_old = {m.from_chapter_id for ms in maps.values() for m in ms}
    old_chapters = {
        c.id: c for c in Chapter.objects.filter(id__in=list(old_rows), is_active=True).select_related("subject")
    }

    def in_order(chapters):
        return sorted(chapters, key=lambda c: (c.subject.sort_order, c.subject.key, c.sort_order, c.key))

    carried = []
    for chapter in in_order(new_chapters[cid] for cid in carried_ids):
        incoming = maps[chapter.id]
        sources = [old_chapters[m.from_chapter_id] for m in incoming if m.from_chapter_id in old_chapters]
        carried.append(
            {
                **_chapter_ref(chapter),
                "relation": ChapterMap.Relation.MERGED if len(incoming) > 1 else incoming[0].relation,
                "from": [_chapter_ref(c) for c in in_order(sources)],
            }
        )
    carried_set = set(carried_ids)
    new = [
        _chapter_ref(c)
        for c in in_order(new_chapters[cid] for cid in new_progress if cid in new_chapters)
        if c.id not in carried_set
    ]
    removed = [_chapter_ref(c) for c in in_order(old_chapters.values()) if c.id not in mapped_old]
    return {
        "carried_chapters": len(carried),
        "new_chapters": len(new),
        "removed_chapters": len(removed),
        "carried": carried,
        "new": new,
        "removed": removed,
    }


# --- rebuild from the ledger -----------------------------------------------------------------


@transaction.atomic
def rebuild_enrollment(enrollment: Enrollment) -> None:
    """Resets all derived data of an enrolment and replays the ledger in time order (admin command and tests)."""
    settings = get_or_create_settings(enrollment.user_id)
    revision_days = selectors.revision_days_of(settings)
    TopicProgress.objects.filter(user_id=enrollment.user_id, enrollment=enrollment).delete()
    progress_by_chapter = {p.chapter_id: p for p in selectors.chapter_progress_for_enrollment(enrollment)}
    for p in progress_by_chapter.values():
        p.practice_count = p.mock_count = p.revision_count = p.total_study_seconds = 0
        p.first_started_at = p.last_studied_at = p.last_revised_at = p.next_revision_due = None
        p.confidence, p.is_excluded, p.implicit_topic_done = "", False, False

    topic_state: dict = {}  # topic_id -> (is_done, when)
    chapter_topics: dict = defaultdict(list)
    for topic_id, chapter_id in Topic.objects.filter(
        chapter_id__in=list(progress_by_chapter), is_active=True
    ).values_list("id", "chapter_id"):
        chapter_topics[chapter_id].append(topic_id)

    events = CoverageEvent.objects.filter(enrollment=enrollment).order_by("occurred_at", "created_at")
    for event in events:
        progress = progress_by_chapter.get(event.chapter_id)
        if progress is None:
            continue
        apply_event(
            progress,
            event.type,
            value=event.value,
            payload=event.payload,
            occurred_at=event.occurred_at,
            revision_days=revision_days,
        )
        if event.type in (EventType.TOPIC_DONE, EventType.TOPIC_UNDONE):
            done = event.type == EventType.TOPIC_DONE
            if event.topic_id:
                targets = [event.topic_id]
            elif event.payload.get("all") or event.payload.get("implicit"):
                targets = chapter_topics.get(event.chapter_id, [])
                if not targets:
                    progress.implicit_topic_done = done
            else:
                targets = []
            for topic_id in targets:
                topic_state[topic_id] = (done, event.occurred_at, event.source)

    TopicProgress.objects.bulk_create(
        [
            TopicProgress(
                user_id=enrollment.user_id,
                topic_id=topic_id,
                enrollment=enrollment,
                is_done=done,
                done_at=when if done else None,
                source=source,
                updated_at=when,
            )
            for topic_id, (done, when, source) in topic_state.items()
        ]
    )
    rows = list(progress_by_chapter.values())
    counts = selectors.topic_counts(enrollment.user_id, [p.chapter_id for p in rows])
    for p in rows:
        _recompute_chapter(p, p.chapter, settings, counts[p.chapter_id])
    ChapterProgress.objects.bulk_update(
        rows,
        [
            "status",
            "read_pct",
            "practice_pct",
            "revise_pct",
            "mock_pct",
            "coverage_pct",
            "practice_count",
            "mock_count",
            "revision_count",
            "total_study_seconds",
            "first_started_at",
            "last_studied_at",
            "last_revised_at",
            "next_revision_due",
            "confidence",
            "is_excluded",
            "implicit_topic_done",
            "updated_at",
        ],
    )
    recompute_rollups(enrollment, rows)


# --- account data ----------------------------------------------------------------------------


@transaction.atomic
def delete_all_for_user(user_id) -> dict:
    """Removes enrolments, progress, events, roll-ups and settings (FR-29). Called by the account deletion flow."""
    enrollments = Enrollment.objects.filter(user_id=user_id)
    summary = {
        "events": CoverageEvent.objects.filter(user_id=user_id).count(),
        "enrollments": enrollments.count(),
    }
    CoverageEvent.objects.filter(user_id=user_id).delete()
    TopicProgress.objects.filter(user_id=user_id).delete()
    ChapterProgress.objects.filter(user_id=user_id).delete()
    Enrollment.objects.filter(user_id=user_id).update(carried_from=None)
    enrollments.delete()  # cascades roll-ups
    CoverageSettings.objects.filter(pk=user_id).delete()
    return summary
