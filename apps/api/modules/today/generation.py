"""
Generation without side effects (PRD 4.2, ERD 3.4): build the context for one student and one local day, run the providers, resolve
their candidates against the registry, and compose the plan. Nothing here writes, so `preview/` and `open/` share it and a preview
can never leave a row behind. `services.py` persists the result.

    context  ->  providers (runner)  ->  candidates  ->  compose()  ->  Generated

A student with no active enrolment gets an empty, valid plan (the web shows "set up your course"). A student whose exam date has
passed (`post_exam`) gets an empty plan without running any provider: there is nothing to prepare for.
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta
from uuid import UUID

from django.utils import timezone

from . import selectors
from .adapters import coverage as coverage_adapter
from .adapters import tracking as tracking_adapter
from .domain import budget as budget_rules
from .domain import compose, phases
from .domain.constants import COMEBACK_MISSED_DAYS
from .models import DayPlan, TodaySettings
from .registry import EnrollmentCtx, PaperCtx, PlanContext, ProviderSpec, TaskCandidate
from .runner import RunResult, run_providers

logger = logging.getLogger(__name__)

ACTIVITY_WINDOW_DAYS = 60  # how far back "has this student studied before" and a paper's last activity look
FREE_HISTORY_DAYS = 14


@dataclass(frozen=True)
class Generated:
    ctx: PlanContext
    compose_ctx: compose.Context
    selection: compose.Selection
    run: RunResult
    budget_source: str
    exam_date: date | None
    context_hash: str
    candidates_by_key: dict[
        str, tuple[ProviderSpec, TaskCandidate]
    ]  # dedupe_key -> who offered it, for the rows we write
    backlogs: tuple[dict, ...]  # what providers said they had more of ("38 revisions are overdue")


# ---- the context ------------------------------------------------------------------------------------------------------------


def _local_date(now: datetime, tz: str) -> date:
    return tracking_adapter.local_date(now, tz)


def student_today(user_id, now: datetime | None = None) -> tuple[date, str]:
    """The student's local date and zone. Read only: a student with no tracker row gets the default zone and nothing is stored."""
    tz = tracking_adapter.timezone_of(user_id)
    return _local_date(now or timezone.now(), tz), tz


def _seed(user_id, local_date: date) -> int:
    return int.from_bytes(hashlib.sha1(f"{user_id}|{local_date.isoformat()}".encode()).digest()[:4], "big")


def _hash(parts: dict) -> str:
    return hashlib.sha256(json.dumps(parts, sort_keys=True, default=str).encode()).hexdigest()


def _comeback(user_id, local_date: date) -> bool:
    """Three complete local days with no tracked time and no done task, for a student who has studied before (PRD 5.7)."""
    since = local_date - timedelta(days=ACTIVITY_WINDOW_DAYS)
    active = tracking_adapter.days_with_time(user_id, since, local_date - timedelta(days=1)) | selectors.done_days(
        user_id, since, local_date - timedelta(days=1)
    )
    recent = [(local_date - timedelta(days=n)) in active for n in range(1, COMEBACK_MISSED_DAYS + 1)]
    return budget_rules.is_comeback(
        recent, had_activity_before=bool(active) or selectors.ever_completed_a_task(user_id)
    )


def build_context(
    user_id,
    local_date: date,
    tz: str,
    *,
    plan: DayPlan | None = None,
    settings: TodaySettings | None = None,
    history: selectors.KeyHistory | None = None,
    is_preview: bool = False,
) -> tuple[PlanContext, compose.Context, str, date | None]:
    """Everything the engine needs, read once. Returns the provider-facing context, the composer's, the budget source and the exam date."""
    settings = settings or selectors.get_settings(user_id)
    enrollment = coverage_adapter.active_enrollment(user_id)
    exam = coverage_adapter.exam_date(enrollment) if enrollment else None
    days_to_exam = phases.days_to_exam(exam, local_date)
    phase = phases.phase_for(days_to_exam)

    budget, source = budget_rules.budget_for(
        setting_minutes=settings.minutes_per_day,
        daily_minutes=coverage_adapter.daily_minutes(enrollment) if enrollment else None,
    )
    comeback = enrollment is not None and _comeback(user_id, local_date)
    if comeback:
        budget, source = budget_rules.comeback_budget(budget), "comeback"
    focus = budget_rules.focus_papers(budget, settings.focus_papers)

    papers: list[PaperCtx] = []
    if enrollment is not None:
        state = coverage_adapter.study_state(user_id, enrollment, tz)
        worked = selectors.last_done_by_subject(user_id, local_date - timedelta(days=ACTIVITY_WINDOW_DAYS))
        for subject in state.subjects:
            touched = [d for d in (subject.last_studied_on, worked.get(subject.subject_id)) if d]
            last = max(touched) if touched else None
            papers.append(
                PaperCtx(
                    subject_id=subject.subject_id,
                    key=subject.key,
                    name=subject.name,
                    paper_number=subject.paper_number,
                    kind=subject.kind,
                    coverage_pct=subject.coverage_pct,
                    days_untouched=(local_date - last).days if last else None,
                )
            )

    history = history or selectors.key_history(user_id, local_date, plan)
    ctx = PlanContext(
        user_id=UUID(str(user_id)),
        local_date=local_date,
        tz=tz,
        enrollment=EnrollmentCtx(
            id=enrollment.id,
            scheme_id=enrollment.scheme_id,
            course_code=enrollment.scheme.level.course.code,
            level_code=enrollment.scheme.level.code,
            exam_date=exam,
            term_code=enrollment.target_term.code if enrollment.target_term else None,
            daily_hours=enrollment.daily_hours,
        )
        if enrollment
        else None,
        days_to_exam=days_to_exam,
        phase=phase,
        papers=tuple(papers),
        done_keys=history.in_plan_keys,
        suppressed_keys=history.suppressed_keys,
        budget_minutes=budget,
        comeback=comeback,
        seed=_seed(user_id, local_date),
        is_preview=is_preview,
    )
    compose_ctx = compose.Context(
        local_date=local_date,
        phase=phase,
        budget_minutes=budget,
        focus_papers=focus,
        max_tasks=budget_rules.task_cap(comeback),
        papers=tuple(compose.PaperInfo(p.key, p.days_untouched) for p in papers),
        days_to_exam=days_to_exam,
        done_keys=history.in_plan_keys,
        suppressed_keys=history.suppressed_keys,
        hidden_kinds=frozenset(settings.disabled_kinds or ()),
        comeback=comeback,
        seed=ctx.seed,
    )
    return ctx, compose_ctx, source, exam


# ---- candidates -------------------------------------------------------------------------------------------------------------


def resolve(run: RunResult, ctx: PlanContext, miss_counts: dict[str, int]) -> tuple[list[compose.Candidate], int]:
    """
    Turns every provider's `TaskCandidate` into the composer's `Candidate` (group and slot come from the registered kind, the paper
    key from the subject). Returns the candidates and how many were unusable (an unknown kind, a malformed value): counted as
    `invalid`, never fatal.
    """
    paper_key = {p.subject_id: p.key for p in ctx.papers}
    out: list[compose.Candidate] = []
    invalid = 0
    for outcome in run.outcomes:
        if outcome.result is None:
            continue
        kinds = {k.name: k for k in outcome.spec.kinds}
        for tc in outcome.result.candidates:
            try:
                kind = kinds[tc.kind]
                key = None if tc.subject_id is None else paper_key.get(tc.subject_id, f"?{tc.subject_id}")
                out.append(
                    compose.Candidate(
                        provider=outcome.spec.name,
                        kind=tc.kind,
                        group=kind.group,
                        slot=kind.slot,
                        dedupe_key=tc.dedupe_key,
                        title=tc.title,
                        reason_code=tc.reason_code,
                        reason=tc.reason,
                        link_path=tc.link.path,
                        link_search=dict(tc.link.search),
                        est_minutes=tc.est_minutes,
                        urgency=tc.signals.urgency,
                        importance=tc.signals.importance,
                        weakness=tc.signals.weakness,
                        freshness=tc.signals.freshness,
                        paper_key=key,
                        target_value=tc.target_value,
                        must_do=bool(tc.must_do),
                        expires_on=tc.expires_on,
                        provider_weight=outcome.weight_pct,
                        miss_count=miss_counts.get(tc.dedupe_key, 0),
                        ref=(outcome.spec, tc),
                    )
                )
            except (KeyError, AttributeError, TypeError):
                logger.warning("today: unusable candidate from %s", outcome.spec.name, exc_info=True)
                invalid += 1
    return out, invalid


def _backlogs(run: RunResult) -> tuple[dict, ...]:
    return tuple(
        {
            "provider": o.spec.name,
            "count": o.result.backlog_count,
            "label": o.result.backlog_label,
            "link": o.result.backlog_link,
        }
        for o in run.outcomes
        if o.result and o.result.backlog_count > 0
    )


# ---- the pipeline -----------------------------------------------------------------------------------------------------------


def generate(user_id, local_date: date, tz: str, *, plan: DayPlan | None = None, is_preview: bool = False) -> Generated:
    """Build the plan for one student and one day without writing anything."""
    history = selectors.key_history(user_id, local_date, plan)
    ctx, compose_ctx, source, exam = build_context(
        user_id, local_date, tz, plan=plan, history=history, is_preview=is_preview
    )
    if ctx.phase == "post_exam" or ctx.enrollment is None:
        run = RunResult()
        selection = compose.compose([], replace(compose_ctx, phase="steady"))
        extra_invalid = 0
    else:
        run = run_providers(ctx)
        candidates, extra_invalid = resolve(run, ctx, history.miss_counts)
        selection = compose.compose(candidates, compose_ctx)
    if extra_invalid:
        dropped = dict(selection.dropped)
        dropped["invalid"] = dropped.get("invalid", 0) + extra_invalid
        selection = replace(selection, dropped=dropped)
    offered = {p.candidate.dedupe_key: p.candidate.ref for p in selection.picks if isinstance(p.candidate.ref, tuple)}
    context_hash = _hash(
        {
            "date": local_date,
            "phase": ctx.phase,
            "budget": ctx.budget_minutes,
            "focus": compose_ctx.focus_papers,
            "papers": [(p.key, p.days_untouched) for p in ctx.papers],
            "in_plan": sorted(ctx.done_keys),
            "suppressed": sorted(ctx.suppressed_keys),
            "hidden": sorted(compose_ctx.hidden_kinds),
            "comeback": ctx.comeback,
            "algorithm": 1,
        }
    )
    return Generated(
        ctx=ctx,
        compose_ctx=compose_ctx,
        selection=selection,
        run=run,
        budget_source=source,
        exam_date=exam,
        context_hash=context_hash,
        candidates_by_key=offered,
        backlogs=_backlogs(run),
    )
