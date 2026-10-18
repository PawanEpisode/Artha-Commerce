"""
Today provider registration for F-11 Paper Priority tasks.
"""

from __future__ import annotations

import logging

from modules.today.registry import (
    DeepLink,
    KindSpec,
    ProviderResult,
    Signals,
    TaskCandidate,
    TaskRequest,
    register_task_provider,
)

logger = logging.getLogger(__name__)

PRIORITY_CHAPTER_KIND = KindSpec(
    name="priority_chapter",
    group="practice",
    slot="practical",
    icon="target",
    default_est_minutes=45,
)


def provide_paper_priority_tasks(req: TaskRequest) -> ProviderResult:
    """Provides priority chapter tasks to Today from active plan."""
    from .selectors import todays_items

    items = todays_items(req.user_id, req.today, limit=req.max_candidates or 4)
    if not items:
        return ProviderResult(candidates=(), backlog_count=0)

    candidates = []
    for it in items:
        candidates.append(
            TaskCandidate(
                kind="priority_chapter",
                dedupe_key=f"pa_plan_item:{it.id}",
                title=f"Target: {it.chapter_key}",
                reason_code="plan_scheduled_today",
                reason=f"High-yield study item scheduled for Day {it.day_number}",
                link=DeepLink("/app/analysis/plan/active"),
                est_minutes=it.target_minutes,
                signals=Signals(
                    urgency=80,
                    importance=int(min(max(float(it.expected_gain) * 10, 0), 100)),
                    weakness=50,
                    freshness=60,
                ),
                subject_id=None,
                chapter_id=it.chapter_id,
            )
        )

    return ProviderResult(candidates=tuple(candidates), backlog_count=len(items))


try:
    register_task_provider(
        name="paperanalysis.priority",
        provide=provide_paper_priority_tasks,
        kinds=(PRIORITY_CHAPTER_KIND,),
        label="High-Yield Chapter Priority",
        flag="paper_analysis_planner",
        timeout_ms=400,
        max_candidates=4,
    )
except Exception as exc:
    logger.debug("Today provider registration deferred: %s", exc)
