"""
Light background work (ERD 3.3, 6.5), run from the cron tick `POST /api/v1/notes/internal/tick/` (or the worker). Handlers are
thin and idempotent; the heavy ones (PDF inspection, OCR, export) arrive with R2 and run in the always-on worker.

    notes.purge             hard-delete notes whose 30 trash days are over, queue their image files for deletion
    notes.thin_versions     keep one autosave a day after the first 24 hours (see domain.retention)
    notes.reconcile_usage   recompute usage counters from the tables and log any drift (should be zero)

Thinning and reconciling walk every note or student, so they run as a chain of small jobs with a cursor, once a day:
each job handles a batch, then queues the next batch under its own key. `tick()` only starts the day's chain.
"""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from core import jobs as core_jobs
from modules.media import services as media

from .domain.retention import VersionInfo, versions_to_delete
from .models import Note, NoteVersion, QuotaUsage, Tag
from .services import trash

logger = logging.getLogger(__name__)

JOB_PURGE = "notes.purge"
JOB_THIN = "notes.thin_versions"
JOB_RECONCILE = "notes.reconcile_usage"
JOB_EXPIRE_UPLOADS = media.JOB_EXPIRE
LIGHT_TYPES = (JOB_PURGE, JOB_THIN, JOB_RECONCILE, JOB_EXPIRE_UPLOADS, media.JOB_DELETE)
BATCH = 200
PURGE_BATCHES = 5
TICK_BUDGET_SECONDS = 20
NOTE_STORAGE_KINDS = ("note_image", "note_pdf")


def register_handlers(jobs_module) -> None:
    jobs_module.register_handler(JOB_PURGE, purge_job)
    jobs_module.register_handler(JOB_THIN, thin_versions_job)
    jobs_module.register_handler(JOB_RECONCILE, reconcile_usage_job)


def purge_job(payload: dict) -> dict:
    purged = 0
    for _ in range(PURGE_BATCHES):
        done = trash.purge_expired(limit=BATCH)
        purged += done
        if done < BATCH:
            break
    return {"purged": purged}


# --- Chains with a cursor -----------------------------------------------------------------------------------------------
def _continue(job_type: str, day: str, after: Any, full: bool) -> None:
    if full:
        core_jobs.enqueue(
            job_type, {"after": str(after), "day": day}, dedupe_key=f"{job_type}:{day}:{after}", once=True
        )


def thin_versions_job(payload: dict) -> dict:
    now, after = timezone.now(), payload.get("after")
    cutoff = now - timedelta(hours=24)
    old = NoteVersion.objects.filter(created_at__lt=cutoff)
    if after:
        old = old.filter(note_id__gt=after)
    note_ids = list(old.order_by("note_id").values_list("note_id", flat=True).distinct()[:BATCH])
    removed = 0
    for note_id in note_ids:
        rows = [VersionInfo(v.id, v.rev, v.source, v.created_at) for v in NoteVersion.objects.filter(note_id=note_id)]
        doomed = versions_to_delete(rows, now)
        if doomed:
            removed += NoteVersion.objects.filter(pk__in=doomed).delete()[0]
    _continue(JOB_THIN, payload.get("day", ""), note_ids[-1] if note_ids else None, len(note_ids) == BATCH)
    return {"notes": len(note_ids), "removed": removed}


def reconcile_usage_job(payload: dict) -> dict:
    after = payload.get("after")
    users = QuotaUsage.objects.all()
    if after:
        users = users.filter(pk__gt=after)
    user_ids = list(users.order_by("pk").values_list("pk", flat=True)[:BATCH])
    drift = sum(_reconcile_user(u) for u in user_ids)
    _continue(JOB_RECONCILE, payload.get("day", ""), user_ids[-1] if user_ids else None, len(user_ids) == BATCH)
    return {"users": len(user_ids), "drifted": drift}


@transaction.atomic
def _reconcile_user(user_id) -> int:
    """Recomputes the counters notes owns from the rows and writes them back. Returns 1 when something had drifted."""
    usage = QuotaUsage.objects.select_for_update().filter(pk=user_id).first()
    if usage is None:
        return 0
    from modules.media.models import Attachment

    actual = {
        "notes_active": Note.objects.filter(user_id=user_id, deleted_at__isnull=True).count(),
        "tags_count": Tag.objects.filter(user_id=user_id).count(),
        "bytes_used": Attachment.objects.filter(user_id=user_id, kind__in=NOTE_STORAGE_KINDS)
        .exclude(status=Attachment.Status.DELETING)
        .aggregate(total=Sum("bytes"))["total"]
        or 0,
    }
    drifted = {k: (getattr(usage, k), v) for k, v in actual.items() if getattr(usage, k) != v}
    if drifted:
        logger.warning("Notes usage drift for a student: %s", drifted)  # counts only, no identifiers or text
    for key, value in actual.items():
        setattr(usage, key, value)
    usage.reconciled_at = timezone.now()
    usage.save()
    return int(bool(drifted))


# --- The tick -----------------------------------------------------------------------------------------------------------
def tick() -> dict:
    """Starts today's chains (once per day), queues the always-due jobs and runs what is due within the time budget."""
    today = timezone.now().date().isoformat()
    core_jobs.enqueue(JOB_PURGE, {}, dedupe_key=JOB_PURGE)
    core_jobs.enqueue(JOB_EXPIRE_UPLOADS, {}, dedupe_key=JOB_EXPIRE_UPLOADS)
    for job_type in (JOB_THIN, JOB_RECONCILE):
        core_jobs.enqueue(job_type, {"day": today}, dedupe_key=f"{job_type}:{today}:start", once=True)
    ran = core_jobs.run_pending(types=LIGHT_TYPES, budget_seconds=TICK_BUDGET_SECONDS, worker="notes-tick")
    pruned = core_jobs.prune_finished()
    return {"ran": ran, "pruned": pruned}
