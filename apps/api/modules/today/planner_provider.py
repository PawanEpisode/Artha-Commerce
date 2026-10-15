"""
The planner provider (FR-F13-50): the day's milestone task, "Read: {chapter}", for a paper that is behind its `finish_reading`
milestone. Registered by Today itself, behind the flag `today_planner` (a student with no plan gets nothing, so the provider costs
one query for everyone else).

A paper is behind when its reading milestone is open and either the plan says it will finish too late (`at_risk`) or its date has
come. The task is `must_do` only when the milestone is overdue by 3 or more days. Pure read, deterministic, only papers in the
request's context.
"""

from __future__ import annotations

from .adapters import coverage as coverage_adapter
from .models import Milestone, StudyPlan
from .planner import constants as pc
from .registry import (
    CompletionRule,
    DeepLink,
    Event,
    KindSpec,
    Match,
    ProviderResult,
    Signals,
    TaskCandidate,
    TaskRequest,
    TaskView,
    register_task_provider,
)

NAME = "today.planner"
FLAG = "today_planner"
KIND = "planner_read"
KINDS = (KindSpec(KIND, "learn", "read", "BookOpen", 30),)
EVENT = "coverage_event_recorded"
READ_EVENTS = ("topic_done", "practice_done")
TITLE_MAX = 80
MIN_MINUTES, MAX_MINUTES = 10, 45


def _clamp(value: float, low: int = 0, high: int = 100) -> int:
    return max(low, min(high, round(value)))


def _next_chapter(subject):
    """A chapter being read first (started, not finished), else the first unread one, in syllabus order."""
    started = [c for c in subject.chapters if 0 < c.read_pct < 100]
    if started:
        return started[0]
    return next((c for c in subject.chapters if c.read_pct < 100), None)


def provide(request: TaskRequest) -> ProviderResult:
    ctx = request.ctx
    if ctx.enrollment is None:
        return ProviderResult(candidates=())
    plan = StudyPlan.objects.filter(user_id=ctx.user_id, status="active", enrollment_id=ctx.enrollment.id).first()
    if plan is None:
        return ProviderResult(candidates=())
    today = ctx.local_date
    behind = [
        m
        for m in Milestone.objects.filter(plan=plan, kind="finish_reading", status__in=pc.OPEN_MILESTONE_STATUSES)
        if m.status == "at_risk" or m.target_date <= today
    ]
    behind.sort(key=lambda m: (m.target_date, m.sort_order, m.subject_key))
    papers = {p.key: p for p in ctx.papers}
    wanted = [m for m in behind if m.subject_key in papers]
    if not wanted:
        return ProviderResult(candidates=())
    enrollment = coverage_adapter.active_enrollment(ctx.user_id)
    if enrollment is None:
        return ProviderResult(candidates=())
    state = coverage_adapter.study_state(ctx.user_id, enrollment, ctx.tz)
    subjects = {s.key: s for s in state.subjects}
    candidates = []
    for milestone in wanted:
        subject, paper = subjects.get(milestone.subject_key), papers[milestone.subject_key]
        chapter = _next_chapter(subject) if subject else None
        if chapter is None:
            continue
        overdue = max(0, (today - milestone.target_date).days)
        if overdue == 0 and milestone.status == "pending":
            reason = f"Reading {paper.name} is due today"
        elif overdue:
            days = "1 day" if overdue == 1 else f"{overdue} days"
            reason = f"Reading {paper.name} was due {days} ago"
        else:
            reason = f"Your plan is behind on {paper.name}"
        left = (chapter.est_study_minutes or 60) * (100 - chapter.read_pct) / 100
        heaviest = max((c.marks_weight for c in subject.chapters), default=1.0)
        title = f"Read: {' '.join(chapter.name.split())}"
        candidates.append(
            TaskCandidate(
                kind=KIND,
                dedupe_key=f"plan_read:{chapter.chapter_id}",
                title=title if len(title) <= TITLE_MAX else title[: TITLE_MAX - 1].rstrip() + "…",
                reason_code="milestone_behind",
                reason=reason[:140],
                link=DeepLink("/app/syllabus", {"chapter": str(chapter.chapter_id)}),
                est_minutes=_clamp(min(left, MAX_MINUTES), MIN_MINUTES, MAX_MINUTES),
                signals=Signals(
                    urgency=_clamp(70 + overdue * 10),
                    importance=_clamp(100 * chapter.marks_weight / heaviest) if heaviest > 0 else 50,
                    weakness=_clamp(100 - subject.coverage_pct),
                    freshness=_clamp((paper.days_untouched if paper.days_untouched is not None else 14) * 7),
                ),
                subject_id=paper.subject_id,
                chapter_id=chapter.chapter_id,
                must_do=overdue >= pc.OVERDUE_MUST_DO_DAYS,
            )
        )
    return ProviderResult(candidates=candidates[: request.limit])


def _match(event: Event, task: TaskView) -> Match | None:
    """Reading a topic of the task's chapter (or practising it) is reading it."""
    same = task.chapter_id is not None and str(event.payload.get("chapter_id")) == str(task.chapter_id)
    if task.kind == KIND and same and event.payload.get("type") in READ_EVENTS:
        return Match(evidence_key=event.key, done=True)
    return None


def register() -> None:
    register_task_provider(
        NAME,
        provide,
        kinds=KINDS,
        label="Study plan",
        flag=FLAG,
        timeout_ms=400,
        max_candidates=8,
        completion=(CompletionRule(EVENT, _match),),
    )
