"""
Background work of recall (ERD 6.4), run by the cron tick `recall/internal/tick/` and idempotent every time:

    recall.exam_horizon   re-evaluate the effective due of one student's cards (payload `user_id`), or walk the students whose exam
                          is within 90 days (or ended in the last week) in batches (payload `after`, `day`), once a day
    recall.sync_subscribers   one chunk of 200 subscriptions of a published deck version (payload `deck_version_id`, `chunk`,
                          `after`): followers are synced, pinned subscriptions record the pending version; queues the next chunk
    recall.sync_subscription  one subscription to the live version (a retry, a pin switched to follow, a resubscribe)
    recall.flag_amendment     the two stages of an F-14 amendment event: platform ribbons, then chips on her own cards (1,000 a chunk)
    recall.scheme_changed     her own cards follow the chapter map after a scheme switch (payload `user_id`, `to_scheme_id`)
    recall.chapter_pass       the chapter recall pass check of one closed session (payload `user_id`, `session_id`)
    recall.expire_suggestions once a day: drafts past 30 days, old batches and the 90-day reject memory go
    recall.suggest            HEAVY, worker only (it waits on Google): one AI suggestion batch (payload `batch_id`, an id only)

The tick claims only `LIGHT_TYPES`. Payloads hold ids and cursors, never text.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any
from uuid import UUID

from django.utils import timezone

from core import jobs as core_jobs

from .adapters import coverage as coverage_adapter
from .domain import limits as lim
from .models import RecallSubscription
from .services import amendments as amendment_service
from .services import chapter_pass as chapter_pass_service
from .services import exam as exam_service
from .services import remap as remap_service
from .services import suggestions as suggestion_service
from .services import sync as sync_service

JOB_EXAM_HORIZON = "recall.exam_horizon"
JOB_SYNC_SUBSCRIBERS = sync_service.JOB_SYNC_SUBSCRIBERS
JOB_SYNC_SUBSCRIPTION = sync_service.JOB_SYNC_SUBSCRIPTION
JOB_FLAG_AMENDMENT = amendment_service.JOB_FLAG_AMENDMENT
JOB_SCHEME_CHANGED = remap_service.JOB_SCHEME_CHANGED
JOB_CHAPTER_PASS = chapter_pass_service.JOB_CHAPTER_PASS
JOB_EXPIRE_SUGGESTIONS = "recall.expire_suggestions"
JOB_SUGGEST = suggestion_service.JOB_SUGGEST  # heavy: only the worker claims it
LIGHT_TYPES = (
    JOB_EXAM_HORIZON,
    JOB_SYNC_SUBSCRIBERS,
    JOB_SYNC_SUBSCRIPTION,
    JOB_FLAG_AMENDMENT,
    JOB_SCHEME_CHANGED,
    JOB_CHAPTER_PASS,
    JOB_EXPIRE_SUGGESTIONS,
)
HEAVY_TYPES = (JOB_SUGGEST,)
assert not set(LIGHT_TYPES) & set(HEAVY_TYPES), "a job type is either light (the tick) or heavy (the worker)"
BATCH = 100
TICK_BUDGET_SECONDS = 20


def register_handlers(jobs_module=core_jobs) -> None:
    jobs_module.register_handler(JOB_EXAM_HORIZON, exam_horizon_job)
    jobs_module.register_handler(JOB_SYNC_SUBSCRIBERS, sync_subscribers_job)
    jobs_module.register_handler(JOB_SYNC_SUBSCRIPTION, sync_subscription_job)
    jobs_module.register_handler(JOB_FLAG_AMENDMENT, amendment_service.run_job)
    jobs_module.register_handler(JOB_SCHEME_CHANGED, scheme_changed_job)
    jobs_module.register_handler(JOB_CHAPTER_PASS, chapter_pass_service.run_job)
    jobs_module.register_handler(JOB_EXPIRE_SUGGESTIONS, suggestion_service.run_expiry)
    jobs_module.register_handler(JOB_SUGGEST, suggestion_service.run_batch)
    jobs_module.register_gave_up_handler(JOB_SUGGEST, suggestion_service.give_up)


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


def sync_subscribers_job(payload: dict) -> dict[str, Any]:
    """One chunk of a deck version's fan-out; a full chunk queues the next (dedupe key `deck_version_id:chunk`)."""
    version_id, chunk = payload["deck_version_id"], int(payload.get("chunk", 0))
    after = UUID(payload["after"]) if payload.get("after") else None
    out = sync_service.sync_chunk(version_id, after)
    if out.next_after is not None:
        core_jobs.enqueue(
            JOB_SYNC_SUBSCRIBERS,
            {"deck_version_id": version_id, "chunk": chunk + 1, "after": str(out.next_after)},
            dedupe_key=f"{JOB_SYNC_SUBSCRIBERS}:{version_id}:{chunk + 1}",
        )
    return {"chunk": chunk, "followed": out.followed, "pinned": out.pinned, "failed": out.failed}


def sync_subscription_job(payload: dict) -> dict[str, Any]:
    row = RecallSubscription.objects.filter(pk=payload["subscription_id"]).values_list("user_id", flat=True).first()
    if row is None:
        return {"changed": False}
    result = sync_service.sync_subscription(
        row, payload["subscription_id"], target_version_id=payload.get("deck_version_id")
    )
    return {"changed": result.changed, "cards": result.cards_updated + result.cards_created}


def scheme_changed_job(payload: dict) -> dict[str, Any]:
    out = remap_service.remap_student(payload["user_id"], UUID(payload["to_scheme_id"]))
    return {"moved": out.moved, "waiting": out.waiting}


def tick() -> dict[str, int]:
    """Starts today's walk (once a day) and runs the light jobs that are due, inside the time budget."""
    today = timezone.now().date().isoformat()
    core_jobs.enqueue(JOB_EXAM_HORIZON, {"day": today}, dedupe_key=f"{JOB_EXAM_HORIZON}:{today}:start", once=True)
    core_jobs.enqueue(JOB_EXPIRE_SUGGESTIONS, {"day": today}, dedupe_key=f"{JOB_EXPIRE_SUGGESTIONS}:{today}", once=True)
    ran = core_jobs.run_pending(types=LIGHT_TYPES, budget_seconds=TICK_BUDGET_SECONDS, worker="recall-tick")
    return {"jobs_ran": ran}
