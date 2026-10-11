"""
Background work of recall (ERD 6.4), run by the cron tick `recall/internal/tick/` and idempotent every time:

    recall.exam_horizon   re-evaluate the effective due of one student's cards (payload `user_id`), or walk the students whose exam
                          is within 90 days (or ended in the last week) in batches (payload `after`, `day`), once a day

The tick claims only `LIGHT_TYPES`. Payloads hold ids and cursors, never text.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from django.utils import timezone

from core import jobs as core_jobs

from .adapters import coverage as coverage_adapter
from .domain import limits as lim
from .services import exam as exam_service

JOB_EXAM_HORIZON = "recall.exam_horizon"
LIGHT_TYPES = (JOB_EXAM_HORIZON,)
BATCH = 100
TICK_BUDGET_SECONDS = 20


def register_handlers(jobs_module=core_jobs) -> None:
    jobs_module.register_handler(JOB_EXAM_HORIZON, exam_horizon_job)


def queue_student(user_id) -> None:
    """One student's cards again, soon (her exam date changed). Merged with a job already waiting for her."""
    core_jobs.enqueue(JOB_EXAM_HORIZON, {"user_id": str(user_id)}, dedupe_key=f"{JOB_EXAM_HORIZON}:u:{user_id}")


def exam_horizon_job(payload: dict) -> dict[str, Any]:
    if payload.get("user_id"):
        return {"users": 1, "changed": exam_service.reevaluate_student(payload["user_id"])}
    today = timezone.now().date()
    first, last = today - timedelta(days=7), today + timedelta(days=lim.EXAM_HORIZON_DAYS + 1)
    after = payload.get("after")
    users = coverage_adapter.exam_audience(first, last, after, BATCH)
    changed = sum(exam_service.reevaluate_student(u) for u in users)
    if len(users) == BATCH:
        day = payload.get("day", today.isoformat())
        core_jobs.enqueue(
            JOB_EXAM_HORIZON,
            {"after": str(users[-1]), "day": day},
            dedupe_key=f"{JOB_EXAM_HORIZON}:{day}:{users[-1]}",
            once=True,
        )
    return {"users": len(users), "changed": changed}


def tick() -> dict[str, int]:
    """Starts today's walk (once a day) and runs the light jobs that are due, inside the time budget."""
    today = timezone.now().date().isoformat()
    core_jobs.enqueue(JOB_EXAM_HORIZON, {"day": today}, dedupe_key=f"{JOB_EXAM_HORIZON}:{today}:start", once=True)
    ran = core_jobs.run_pending(types=LIGHT_TYPES, budget_seconds=TICK_BUDGET_SECONDS, worker="recall-tick")
    return {"jobs_ran": ran}
