"""
What coverage offers Today (F-13 PRD 4.3, ERD 3.2): chapters due for revision, the next topic of a chapter in progress, and the
next chapter to start. Coverage owns the knowledge; Today only receives candidates and decides how many to show.

Two providers, registered from `CoverageConfig.ready()`:

- `coverage.revision`: `revise_chapter`, one per chapter whose `next_revision_due` has arrived. A big backlog is reported as
  `backlog_count` with a link to the revision page, never as 38 tasks.
- `coverage.syllabus`: `next_topic` (a chapter in progress has an undone topic) or `next_chapter` (nothing in progress, the next
  chapter in syllabus order), at most one per paper.

Both are pure reads of `selectors.study_state`, deterministic for the same request, and offer only papers in `ctx.papers`. Dates
are the student's local dates (the plan's), so "overdue" is what the student sees on their calendar (audit AUD-018: the stored
`next_revision_due` itself is derived from the UTC date of the event; see `docs/F-13-BUILD-WAVES.md`).
"""

from __future__ import annotations

import logging
import uuid

from modules.today.registry import (
    DeepLink,
    KindSpec,
    ManualAction,
    ManualActionRef,
    ProviderResult,
    Signals,
    TaskCandidate,
    TaskRequest,
    TaskView,
    register_task_provider,
)

from . import selectors, services
from .errors import CoverageError
from .models import CoverageEvent

logger = logging.getLogger(__name__)

REVISION = "coverage.revision"
SYLLABUS = "coverage.syllabus"
LOG_REVISION = "coverage.log_revision"

_NAMESPACE = uuid.UUID("0b4f6f4e-8e0a-4f3b-9d0e-5d2f7a1c9b77")
TITLE_MAX = 80
REVISION_MIN_MINUTES, REVISION_MAX_MINUTES, REVISION_DEFAULT_MINUTES = 10, 45, 20
TOPIC_MIN_MINUTES, TOPIC_MAX_MINUTES, TOPIC_DEFAULT_MINUTES = 10, 45, 20
CHAPTER_DEFAULT_MINUTES = 30

KINDS_REVISION = (KindSpec("revise_chapter", "revise", "revision", "RefreshCw", REVISION_DEFAULT_MINUTES),)
KINDS_SYLLABUS = (
    KindSpec("next_topic", "learn", "read", "BookOpen", TOPIC_DEFAULT_MINUTES),
    KindSpec("next_chapter", "learn", "read", "BookMarked", CHAPTER_DEFAULT_MINUTES),
)


def _clamp(value: float, low: int = 0, high: int = 100) -> int:
    return max(low, min(high, round(value)))


def _title(prefix: str, name: str) -> str:
    text = f"{prefix} {' '.join(name.split())}"
    return text if len(text) <= TITLE_MAX else text[: TITLE_MAX - 1].rstrip() + "…"


def _importance(weight: float, heaviest: float) -> int:
    """How many marks the chapter carries, relative to the heaviest chapter of its paper."""
    return _clamp(100 * weight / heaviest) if heaviest > 0 else 50


def _days_since(moment, today) -> int | None:
    return (today - moment).days if moment else None


def _papers(request: TaskRequest, state: selectors.StudyState) -> dict:
    wanted = {p.subject_id for p in request.ctx.papers}
    return {s.subject_id: s for s in state.subjects if s.subject_id in wanted}


def _state(request: TaskRequest) -> selectors.StudyState | None:
    ctx = request.ctx
    if ctx.enrollment is None:
        return None
    enrollment = selectors.get_active_enrollment(ctx.user_id, ctx.enrollment.id)
    return selectors.study_state(ctx.user_id, enrollment, ctx.tz) if enrollment else None


# ---- revision ---------------------------------------------------------------------------------------------------------------


def revision_candidates(request: TaskRequest) -> ProviderResult:
    state = _state(request)
    if state is None:
        return ProviderResult(candidates=())
    today = request.ctx.local_date
    due = []
    for subject in _papers(request, state).values():
        heaviest = max((c.marks_weight for c in subject.chapters), default=1.0)
        for chapter in subject.chapters:
            if chapter.next_revision_due and chapter.next_revision_due <= today:
                due.append((subject, chapter, heaviest))
    # most overdue first, then the heavier chapter, then a stable key: the same request always gives the same list
    due.sort(key=lambda row: (row[1].next_revision_due, -row[1].marks_weight, str(row[1].chapter_id)))
    limit = min(request.limit, 50)
    candidates = []
    for subject, chapter, heaviest in due[:limit]:
        overdue = (today - chapter.next_revision_due).days
        number = chapter.revision_count + 1
        if overdue <= 0:
            code, reason = "revision_due_today", f"Revision {number} is due today"
        else:
            days = "1 day" if overdue == 1 else f"{overdue} days"
            code, reason = "revision_overdue", f"Revision {number} was due {days} ago"
        studied = _days_since(chapter.last_studied_on, today)
        estimate = chapter.est_study_minutes * 0.4 if chapter.est_study_minutes else REVISION_DEFAULT_MINUTES
        candidates.append(
            TaskCandidate(
                kind="revise_chapter",
                dedupe_key=f"revise:{chapter.chapter_id}:{number}",
                title=_title("Revise", chapter.name),
                reason_code=code,
                reason=reason,
                link=DeepLink("/app/revision", {"chapter": str(chapter.chapter_id)}),
                est_minutes=_clamp(estimate, REVISION_MIN_MINUTES, REVISION_MAX_MINUTES),
                signals=Signals(
                    urgency=_clamp(40 + overdue * 10),
                    importance=_importance(chapter.marks_weight, heaviest),
                    weakness=_clamp(100 - chapter.coverage_pct),
                    freshness=_clamp((studied or 0) * 4),
                ),
                subject_id=subject.subject_id,
                chapter_id=chapter.chapter_id,
                manual_action=ManualActionRef(LOG_REVISION, "Also log this revision", True),
            )
        )
    return ProviderResult(
        candidates=candidates,
        backlog_count=max(len(due) - len(candidates), 0),
        backlog_label="revisions are overdue",
        backlog_link=DeepLink("/app/revision"),
    )


# ---- syllabus: next topic, next chapter -------------------------------------------------------------------------------------


def _in_progress(subject: selectors.SubjectState):
    """The first chapter (syllabus order) that has been started, is not finished and still has an undone topic."""
    for chapter in subject.chapters:
        if chapter.next_topic and 0 < chapter.coverage_pct < 100 and chapter.status != "not_started":
            return chapter
    return None


def _next_unstarted(subject: selectors.SubjectState):
    for chapter in subject.chapters:
        if chapter.status == "not_started" and chapter.coverage_pct == 0:
            return chapter
    return None


def syllabus_candidates(request: TaskRequest) -> ProviderResult:
    state = _state(request)
    if state is None:
        return ProviderResult(candidates=())
    today = request.ctx.local_date
    days_to_exam = request.ctx.days_to_exam
    close = days_to_exam is not None and days_to_exam <= 30
    candidates = []
    for subject in sorted(_papers(request, state).values(), key=lambda s: (s.coverage_pct, s.key)):
        heaviest = max((c.marks_weight for c in subject.chapters), default=1.0)
        quiet = _days_since(subject.last_studied_on, today)
        freshness = _clamp((quiet if quiet is not None else 14) * 7)
        chapter = _in_progress(subject)
        if chapter is not None:
            topic = chapter.next_topic
            per_topic = (chapter.est_study_minutes or 0) / max(chapter.topics_total, 1)
            candidates.append(
                TaskCandidate(
                    kind="next_topic",
                    dedupe_key=f"topic:{topic.id}",
                    title=_title("Study", topic.name),
                    reason_code="next_in_syllabus",
                    reason=f"Next in {chapter.name}"[:140],
                    link=DeepLink("/app/syllabus", {"chapter": str(chapter.chapter_id), "topic": str(topic.id)}),
                    est_minutes=_clamp(per_topic or TOPIC_DEFAULT_MINUTES, TOPIC_MIN_MINUTES, TOPIC_MAX_MINUTES),
                    signals=Signals(
                        urgency=60 if close else 30,
                        importance=_importance(chapter.marks_weight, heaviest),
                        weakness=_clamp(100 - subject.coverage_pct),
                        freshness=freshness,
                    ),
                    subject_id=subject.subject_id,
                    chapter_id=chapter.chapter_id,
                )
            )
            continue
        chapter = _next_unstarted(subject)
        if chapter is not None:
            candidates.append(
                TaskCandidate(
                    kind="next_chapter",
                    dedupe_key=f"chapter:{chapter.chapter_id}",
                    title=_title("Start", chapter.name),
                    reason_code="not_practised_yet" if subject.coverage_pct else "next_in_syllabus",
                    reason=f"The next chapter of {subject.name}"[:140],
                    link=DeepLink("/app/syllabus", {"chapter": str(chapter.chapter_id)}),
                    est_minutes=_clamp(
                        min(chapter.est_study_minutes or CHAPTER_DEFAULT_MINUTES, 45), TOPIC_MIN_MINUTES, 45
                    ),
                    signals=Signals(
                        urgency=60 if close else 25,
                        importance=_importance(chapter.marks_weight, heaviest),
                        weakness=_clamp(100 - subject.coverage_pct),
                        freshness=freshness,
                    ),
                    subject_id=subject.subject_id,
                    chapter_id=chapter.chapter_id,
                )
            )
    return ProviderResult(candidates=candidates[: request.limit])


# ---- ticking a revision by hand also logs it --------------------------------------------------------------------------------


def log_revision(user_id, task: TaskView) -> None:
    """
    Idempotent: the ledger `client_id` is derived from the task id, so ticking, undoing and ticking again logs one revision. A
    chapter that already reached its target is not an error here, the student did revise it.
    """
    if task.chapter_id is None:
        return
    try:
        services.record_event(
            user_id,
            task.chapter_id,
            CoverageEvent.Type.REVISION_DONE,
            source=CoverageEvent.Source.MANUAL,
            client_id=uuid.uuid5(_NAMESPACE, str(task.id)),
            source_ref="today",
            strict=False,
        )
    except CoverageError:  # pragma: no cover - a capped manual log is refused; the tick still stands
        logger.info("today: revision for task %s was already at its target", task.id)


def register() -> None:
    register_task_provider(
        REVISION,
        revision_candidates,
        kinds=KINDS_REVISION,
        label="Revision",
        timeout_ms=400,
        max_candidates=20,
        manual_actions=[ManualAction(LOG_REVISION, "Also log this revision", True, log_revision)],
    )
    register_task_provider(
        SYLLABUS,
        syllabus_candidates,
        kinds=KINDS_SYLLABUS,
        label="Syllabus",
        timeout_ms=400,
        max_candidates=12,
    )
