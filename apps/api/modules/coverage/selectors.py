"""Read-only queries for coverage. Every function takes `user_id` and filters on it; another student's id is never found."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from uuid import UUID
from zoneinfo import ZoneInfo

from django.db.models import Q, QuerySet
from django.db.models.functions import Coalesce

from modules.syllabus.models import Chapter, Scheme, Subject, SyllabusGroup, Topic

from .domain import targets
from .domain.formula import DEFAULT_REVISION_DAYS, Weights
from .models import ChapterProgress, CoverageEvent, CoverageSettings, Enrollment, Rollup, TopicProgress


def get_active_enrollment(user_id, enrollment_id=None) -> Enrollment | None:
    qs = Enrollment.objects.select_related("scheme__level__course", "target_term").filter(
        user_id=user_id, status=Enrollment.Status.ACTIVE
    )
    if enrollment_id:
        qs = qs.filter(pk=enrollment_id)
    return qs.order_by("-created_at").first()


def exam_date_of(enrollment: Enrollment) -> date | None:
    """The student's own exam date, else the start of the term they chose (one rule for every module that counts down)."""
    return enrollment.exam_date or (enrollment.target_term.exam_start if enrollment.target_term else None)


@dataclass(frozen=True)
class CourseSummary:
    """The student's course in one read-only value: what `/me/`, the workspace home and other modules show."""

    enrollment_id: str
    scheme_id: str
    course_code: str
    course_name: str
    level_code: str
    level_name: str
    term_code: str | None
    term_name: str | None
    exam_date: date | None
    days_remaining: int | None
    daily_minutes: int | None


def course_summary(user_id, today: date | None = None, enrollment: Enrollment | None = None) -> CourseSummary | None:
    """
    The active enrolment as a summary (F-16: "the student's course" has one source of truth). `exam_date` falls back to
    the start of the chosen term. Pass `enrollment` when it is already loaded to avoid a second query.
    """
    enrollment = enrollment or get_active_enrollment(user_id)
    if enrollment is None:
        return None
    today = today or date.today()
    exam_date = exam_date_of(enrollment)
    level = enrollment.scheme.level
    term = enrollment.target_term
    return CourseSummary(
        enrollment_id=str(enrollment.id),
        scheme_id=str(enrollment.scheme_id),
        course_code=level.course.code,
        course_name=level.course.name,
        level_code=level.code,
        level_name=level.name,
        term_code=term.code if term else None,
        term_name=term.name if term else None,
        exam_date=exam_date,
        days_remaining=max((exam_date - today).days, 0) if exam_date else None,
        daily_minutes=enrollment.planned_minutes,
    )


def get_term(term_id):
    """An exam term by id (any level), or None. `update_enrollment` checks it belongs to the enrolment's level."""
    from modules.syllabus.models import ExamTerm

    return ExamTerm.objects.filter(pk=term_id).first() if term_id else None


def scheme_level_id(scheme_id):
    scheme = Scheme.objects.filter(pk=scheme_id).only("level_id").first()
    return scheme.level_id if scheme else None


def get_enrollment(user_id, enrollment_id) -> Enrollment | None:
    return (
        Enrollment.objects.select_related("scheme__level__course", "target_term")
        .filter(user_id=user_id, pk=enrollment_id)
        .first()
    )


def list_enrollments(user_id) -> QuerySet[Enrollment]:
    return (
        Enrollment.objects.select_related("scheme__level__course", "target_term")
        .filter(user_id=user_id)
        .order_by("-created_at")
    )


def get_active_enrollment_for_scheme(user_id, scheme_id) -> Enrollment | None:
    return Enrollment.objects.filter(user_id=user_id, scheme_id=scheme_id, status=Enrollment.Status.ACTIVE).first()


def get_settings(user_id) -> CoverageSettings | None:
    return CoverageSettings.objects.filter(pk=user_id).first()


def weights_of(settings: CoverageSettings) -> Weights:
    return Weights(settings.w_read, settings.w_practice, settings.w_revise, settings.w_mock)


def targets_of(settings: CoverageSettings) -> targets.Targets:
    return targets.Targets(settings.target_practice_sets, settings.target_revisions, settings.target_mocks)


def get_targets(user_id) -> targets.Targets:
    """The student's activity targets, or the pre-F-16 defaults when they never opened settings. Creates nothing."""
    settings = get_settings(user_id)
    return targets_of(settings) if settings else targets.DEFAULT_TARGETS


def revision_days_of(settings: CoverageSettings) -> list[int]:
    return list(settings.revision_days or DEFAULT_REVISION_DAYS)


def chapter_progress_for_enrollment(enrollment: Enrollment) -> QuerySet[ChapterProgress]:
    return ChapterProgress.objects.filter(enrollment=enrollment).select_related("chapter__subject")


def get_chapter_progress(user_id, chapter_id) -> ChapterProgress | None:
    return (
        ChapterProgress.objects.select_related("chapter__subject__scheme__level__course", "enrollment")
        .filter(user_id=user_id, chapter_id=chapter_id, enrollment__status=Enrollment.Status.ACTIVE)
        .first()
    )


def activity_summary(student_targets: targets.Targets, progress: ChapterProgress | None) -> dict:
    """
    Per activity: `done` (never above `target`), `target`, `logged` (the real count) and `can_log`. The target is the
    student's own (F-16), the same for every chapter. Rows that hold more than the target show a full bar and block
    further manual logs; nothing is deleted.
    """
    counts = {
        "practice": progress.practice_count if progress else 0,
        "revisions": progress.revision_count if progress else 0,
        "mocks": progress.mock_count if progress else 0,
    }
    target_of = {
        "practice": student_targets.practice_sets,
        "revisions": student_targets.revisions,
        "mocks": student_targets.mocks,
    }
    return {key: targets.activity_progress(counts[key], target_of[key]) for key in counts}


def confidence_gate(progress: ChapterProgress | None) -> dict:
    """Whether confidence can be rated now, with the numbers the UI needs for its hint."""
    current = progress.coverage_pct if progress else 0
    return {
        "unlocked": targets.confidence_allowed(current),
        "required_pct": targets.CONFIDENCE_MIN_PCT,
        "current_pct": current,
    }


def topic_counts(user_id, chapter_ids) -> dict:
    """{chapter_id: (topics_total, topics_done)} for active topics. Chapters without topics map to (0, 0)."""
    totals: dict = defaultdict(int)
    topic_chapter: dict = {}
    for topic_id, chapter_id in Topic.objects.filter(chapter_id__in=chapter_ids, is_active=True).values_list(
        "id", "chapter_id"
    ):
        totals[chapter_id] += 1
        topic_chapter[topic_id] = chapter_id
    done: dict = defaultdict(int)
    for topic_id in TopicProgress.objects.filter(
        user_id=user_id, topic_id__in=list(topic_chapter), is_done=True
    ).values_list("topic_id", flat=True):
        done[topic_chapter[topic_id]] += 1
    return {cid: (totals.get(cid, 0), done.get(cid, 0)) for cid in chapter_ids}


def topic_states(user_id, chapter_id) -> dict:
    """{topic_id: is_done} for the topics of one chapter."""
    topic_ids = list(Topic.objects.filter(chapter_id=chapter_id, is_active=True).values_list("id", flat=True))
    return dict(
        TopicProgress.objects.filter(user_id=user_id, topic_id__in=topic_ids).values_list("topic_id", "is_done")
    )


def rollups_for_enrollment(enrollment: Enrollment) -> dict[tuple[str, object], Rollup]:
    return {(r.node_type, r.node_id): r for r in Rollup.objects.filter(enrollment=enrollment)}


def overview(enrollment: Enrollment) -> dict:
    """Level, group and subject percents straight from the rollup cache (no chapter scan)."""
    scheme = enrollment.scheme
    rollups = rollups_for_enrollment(enrollment)
    groups = list(SyllabusGroup.objects.filter(scheme=scheme).order_by("sort_order", "key"))
    subjects = list(Subject.objects.filter(scheme=scheme, is_active=True).order_by("sort_order", "key"))
    excluded_by_subject: dict = defaultdict(int)
    for subject_id in ChapterProgress.objects.filter(enrollment=enrollment, is_excluded=True).values_list(
        "chapter__subject_id", flat=True
    ):
        excluded_by_subject[subject_id] += 1
    return {
        "scheme": scheme,
        "level_rollup": rollups.get(("level", scheme.level_id)),
        "groups": [(g, rollups.get(("group", g.id))) for g in groups],
        "subjects": [(s, rollups.get(("subject", s.id)), excluded_by_subject.get(s.id, 0)) for s in subjects],
    }


def subject_chapter_rows(
    enrollment: Enrollment, subject_id
) -> list[tuple[Chapter, ChapterProgress | None, tuple[int, int]]]:
    chapters = list(Chapter.objects.filter(subject_id=subject_id, subject__scheme=enrollment.scheme, is_active=True))
    chapters.sort(key=lambda c: (c.sort_order, c.key))
    progress = {p.chapter_id: p for p in ChapterProgress.objects.filter(enrollment=enrollment, chapter__in=chapters)}
    counts = topic_counts(enrollment.user_id, [c.id for c in chapters])
    return [(c, progress.get(c.id), counts[c.id]) for c in chapters]


def chapter_events(user_id, chapter_id, limit: int = 20) -> QuerySet[CoverageEvent]:
    return CoverageEvent.objects.filter(user_id=user_id, chapter_id=chapter_id).order_by("-occurred_at", "-created_at")[
        :limit
    ]


def revision_history(user_id, chapter_id) -> QuerySet[CoverageEvent]:
    return CoverageEvent.objects.filter(
        user_id=user_id, chapter_id=chapter_id, type=CoverageEvent.Type.REVISION_DONE
    ).order_by("-occurred_at")


def due_for_revision(enrollment: Enrollment, today: date) -> list[ChapterProgress]:
    """Overdue first, then heavier chapters first (ordering is done in Python: the set is at most a level's chapters)."""
    rows = list(
        ChapterProgress.objects.select_related("chapter__subject")
        .filter(
            enrollment=enrollment,
            is_excluded=False,
            next_revision_due__isnull=False,
            next_revision_due__lte=today,
        )
        .order_by("next_revision_due")
    )
    rows.sort(key=lambda p: ((today - p.next_revision_due).days * -1, -p.chapter.marks_weight))
    return rows


def audience_user_ids(*, level_id=None, course_id=None, after=None, limit: int = 500) -> list:
    """
    Students with an active enrolment on this level (or any level of this course), in `user_id` order, one page at a
    time: pass the last id of the previous page as `after`. For other modules that need to reach a cohort (new content)
    without reading enrolments themselves.
    """
    rows = Enrollment.objects.filter(status=Enrollment.Status.ACTIVE)
    if level_id is not None:
        rows = rows.filter(level_id=level_id)
    elif course_id is not None:
        rows = rows.filter(level__course_id=course_id)
    else:
        return []
    if after is not None:
        rows = rows.filter(user_id__gt=after)
    return list(rows.order_by("user_id").values_list("user_id", flat=True).distinct()[:limit])


def exam_audience(*, first: date, last: date, after=None, limit: int = 200) -> list:
    """
    Students whose active enrolment has an exam date (their own, else the start of the term they chose) from `first` to
    `last`, in `user_id` order, one page at a time (pass the last id as `after`). For nightly jobs of other modules.
    """
    rows = Enrollment.objects.filter(status=Enrollment.Status.ACTIVE).annotate(
        exam=Coalesce("exam_date", "target_term__exam_start")
    )
    rows = rows.filter(exam__gte=first, exam__lte=last)
    if after is not None:
        rows = rows.filter(user_id__gt=after)
    return list(rows.order_by("user_id").values_list("user_id", flat=True).distinct()[:limit])


def last_studied(enrollment: Enrollment) -> ChapterProgress | None:
    """The chapter the student touched most recently (any activity), for "Continue where you left off"."""
    return (
        ChapterProgress.objects.select_related("chapter__subject")
        .filter(enrollment=enrollment, is_excluded=False, last_studied_at__isnull=False)
        .order_by("-last_studied_at")
        .first()
    )


def export_all(user_id) -> dict:
    """Everything coverage stores about the student (FR-29)."""
    settings = get_settings(user_id)
    return {
        "settings": None
        if settings is None
        else {
            "w_read": settings.w_read,
            "w_practice": settings.w_practice,
            "w_revise": settings.w_revise,
            "w_mock": settings.w_mock,
            "revision_days": revision_days_of(settings),
            "weighted_default": settings.weighted_default,
            "targets": {
                "practice_sets": settings.target_practice_sets,
                "revisions": settings.target_revisions,
                "mocks": settings.target_mocks,
                "preset": settings.targets_preset,
                "confirmed_at": settings.targets_confirmed_at.isoformat() if settings.targets_confirmed_at else None,
            },
        },
        "enrollments": [
            {
                "id": str(e.id),
                "scheme": f"{e.scheme.level.course.code}/{e.scheme.level.code}/{e.scheme.code}",
                "status": e.status,
                "target_term": e.target_term.code if e.target_term else None,
                "exam_date": e.exam_date.isoformat() if e.exam_date else None,
                "daily_minutes": e.planned_minutes,
                "electives": {x.slot_key: x.subject.key for x in e.electives.select_related("subject")},
            }
            for e in list_enrollments(user_id)
        ],
        "chapter_progress": [
            {
                "enrollment": str(p.enrollment_id),
                "chapter": f"{p.chapter.subject.key}/{p.chapter.key}",
                "status": p.status,
                "coverage_pct": p.coverage_pct,
                "confidence": p.confidence,
                "is_excluded": p.is_excluded,
                "practice_count": p.practice_count,
                "mock_count": p.mock_count,
                "revision_count": p.revision_count,
                "total_study_seconds": p.total_study_seconds,
                "notes_count": p.notes_count,
                "has_summary": p.has_summary,
                "next_revision_due": p.next_revision_due.isoformat() if p.next_revision_due else None,
            }
            for p in ChapterProgress.objects.filter(user_id=user_id).select_related("chapter__subject")
        ],
        "topic_progress": [
            {"topic": f"{t.topic.chapter.key}/{t.topic.key}", "is_done": t.is_done, "source": t.source}
            for t in TopicProgress.objects.filter(user_id=user_id).select_related("topic__chapter")
        ],
        "events": [
            {
                "type": e.type,
                "chapter": f"{e.chapter.subject.key}/{e.chapter.key}",
                "value": float(e.value) if e.value is not None else None,
                "source": e.source,
                "payload": e.payload,
                "occurred_at": e.occurred_at.isoformat(),
            }
            for e in CoverageEvent.objects.filter(user_id=user_id)
            .select_related("chapter__subject")
            .order_by("occurred_at")
        ],
    }


def scheme_chapter_ids(scheme: Scheme) -> list:
    return list(Chapter.objects.filter(subject__scheme=scheme, is_active=True).values_list("id", flat=True))


def coverage_pct_by_chapter(user_id, chapter_ids) -> dict:
    """Coverage percent per chapter id, for the chapters the student has progress on (used by tracking reports)."""
    return dict(
        ChapterProgress.objects.filter(user_id=user_id, chapter_id__in=list(chapter_ids)).values_list(
            "chapter_id", "coverage_pct"
        )
    )


def started_chapter_ids(user_id, chapter_ids) -> set:
    """Of these chapters, the ones the student has started: a status other than `not_started` or any coverage."""
    ids = list(chapter_ids)
    if not ids:
        return set()
    started = ChapterProgress.objects.filter(user_id=user_id, chapter_id__in=ids, is_excluded=False).filter(
        ~Q(status=ChapterProgress.Status.NOT_STARTED) | Q(coverage_pct__gt=0)
    )
    return set(started.values_list("chapter_id", flat=True))


def progress_stamp(user_id) -> tuple:
    """A cheap version stamp of the student's chapter progress, for report ETags that include coverage."""
    from django.db.models import Count, Max

    agg = ChapterProgress.objects.filter(user_id=user_id).aggregate(n=Count("id"), latest=Max("updated_at"))
    return agg["n"], agg["latest"]


def tracked_study_seconds(user_id, source_refs) -> dict[tuple[str, object], int]:
    """Net study seconds forwarded by tracking per (source_ref, chapter_id): originals plus signed corrections."""
    totals: dict[tuple[str, object], int] = defaultdict(int)
    rows = CoverageEvent.objects.filter(
        user_id=user_id, type="study_time", source="tracking", source_ref__in=[str(r) for r in source_refs]
    ).values_list("source_ref", "chapter_id", "value")
    for ref, chapter_id, value in rows:
        totals[(ref, chapter_id)] += int(value or 0)
    return dict(totals)


# ---- the student's study state as plain data (F-13 Today, and any module that plans a day) ----------------------------------


@dataclass(frozen=True)
class NextTopic:
    id: object
    key: str
    name: str


@dataclass(frozen=True)
class ChapterState:
    chapter_id: object
    key: str
    name: str
    section: str
    subject_id: object
    sort_order: int
    marks_weight: float
    est_study_minutes: int | None
    status: str
    coverage_pct: int
    read_pct: int
    revision_count: int
    next_revision_due: date | None
    last_studied_on: date | None  # the student's local date, never UTC
    topics_total: int
    topics_done: int
    next_topic: NextTopic | None  # the first active topic not done, in syllabus order


@dataclass(frozen=True)
class SubjectState:
    subject_id: object
    key: str
    name: str
    paper_number: int | None
    kind: str
    coverage_pct: int
    last_studied_on: date | None
    chapters: tuple[ChapterState, ...]  # active, not excluded, in syllabus order


@dataclass(frozen=True)
class StudyState:
    enrollment_id: object
    scheme_id: object
    subjects: tuple[SubjectState, ...]  # only papers the student studies (excluded electives are absent)
    had_activity: bool


def study_state(user_id, enrollment: Enrollment, tz: str = "UTC") -> StudyState:
    """
    One read of what the student has and has not covered, as frozen values with no models in them. Dates are the student's
    local dates (`tz`), so "days untouched" and "overdue" mean what the student sees on their calendar. Three queries.
    """
    zone = ZoneInfo(tz)

    def local(moment):
        return moment.astimezone(zone).date() if moment else None

    chapters = list(
        Chapter.objects.filter(subject__scheme=enrollment.scheme, subject__is_active=True, is_active=True)
        .select_related("subject")
        .order_by("subject__sort_order", "subject__key", "sort_order", "key")
    )
    progress = {
        p.chapter_id: p
        for p in ChapterProgress.objects.filter(enrollment=enrollment, chapter_id__in=[c.id for c in chapters])
    }
    topics: dict = defaultdict(list)
    for t in Topic.objects.filter(chapter_id__in=[c.id for c in chapters], is_active=True).order_by(
        "sort_order", "key"
    ):
        topics[t.chapter_id].append(t)
    done_ids = set(
        TopicProgress.objects.filter(user_id=user_id, topic__chapter__in=chapters, is_done=True).values_list(
            "topic_id", flat=True
        )
    )
    rollups = rollups_for_enrollment(enrollment)

    by_subject: dict = defaultdict(list)
    subjects: dict = {}
    for c in chapters:
        p = progress.get(c.id)
        if p is not None and p.is_excluded:
            continue
        subjects[c.subject_id] = c.subject
        rows = topics.get(c.id, [])
        next_topic = next((NextTopic(t.id, t.key, t.name) for t in rows if t.id not in done_ids), None)
        by_subject[c.subject_id].append(
            ChapterState(
                chapter_id=c.id,
                key=c.key,
                name=c.name,
                section=c.section,
                subject_id=c.subject_id,
                sort_order=c.sort_order,
                marks_weight=c.marks_weight,
                est_study_minutes=c.est_study_minutes,
                status=p.status if p else ChapterProgress.Status.NOT_STARTED,
                coverage_pct=p.coverage_pct if p else 0,
                read_pct=p.read_pct if p else 0,
                revision_count=p.revision_count if p else 0,
                next_revision_due=p.next_revision_due if p else None,
                last_studied_on=local(p.last_studied_at) if p else None,
                topics_total=len(rows),
                topics_done=sum(1 for t in rows if t.id in done_ids),
                next_topic=next_topic,
            )
        )
    out = []
    for subject_id, rows in by_subject.items():
        s = subjects[subject_id]
        rollup = rollups.get(("subject", subject_id))
        touched = [r.last_studied_on for r in rows if r.last_studied_on]
        out.append(
            SubjectState(
                subject_id=subject_id,
                key=s.key,
                name=s.name,
                paper_number=s.paper_number,
                kind=s.kind,
                coverage_pct=rollup.pct_simple if rollup else 0,
                last_studied_on=max(touched) if touched else None,
                chapters=tuple(rows),
            )
        )
    return StudyState(
        enrollment_id=enrollment.id,
        scheme_id=enrollment.scheme_id,
        subjects=tuple(out),
        had_activity=any(r.last_studied_on for sub in out for r in sub.chapters),
    )


# ---- F-11 Paper Analysis extension -----------------------------------------------------------


@dataclass(frozen=True)
class ExamContext:
    enrollment_id: UUID
    scheme_id: UUID
    level_id: UUID
    exam_date: date | None
    term_code: str | None
    daily_hours: float | None
    subject_ids: list[UUID]


def exam_context(user_id: UUID, enrollment_id: UUID | None = None) -> ExamContext | None:
    """The student's study context for analysis and planning."""
    enr = get_active_enrollment(user_id, enrollment_id=enrollment_id)
    if enr is None:
        return None
    exam_date = exam_date_of(enr)
    subject_ids = list(enr.scheme.subjects.filter(is_active=True).values_list("id", flat=True))
    daily_hours = float(enr.daily_minutes / 60.0) if enr.daily_minutes else None
    term_code = enr.target_term.code if enr.target_term else None
    return ExamContext(
        enrollment_id=enr.id,
        scheme_id=enr.scheme_id,
        level_id=enr.scheme.level_id,
        exam_date=exam_date,
        term_code=term_code,
        daily_hours=daily_hours,
        subject_ids=subject_ids,
    )

