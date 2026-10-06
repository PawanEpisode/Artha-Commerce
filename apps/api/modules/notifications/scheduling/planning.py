"""
Planning and cancelling exact-time jobs (ERD 2.6). All the writes that put a job on the calendar live here; firing a job
is `jobs.py`. The split keeps `services.notify` (which plans a deferred send) free of the firing code, which imports it.

Reliability rules:
  * Every plan is an upsert on the unique key (student, kind, subject, version): replaying an event plans nothing new.
  * Publishing to the queue happens after the row exists and never raises into the caller (a student's write must not
    fail because a queue is down). A job whose message never arrived is fired by the sweep.
  * A job that is already past `pending` is returned untouched and nothing is published for it.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from datetime import datetime
from typing import Any

from django.db import transaction
from django.utils import timezone

from ..domain.enums import JobKind, JobStatus
from ..logs import log_event
from ..models import Notification, ScheduledJob
from . import queue

#: A held notification is planned again each time its send finds quiet hours still on (the student moved them). The expiry
#: bounds this in practice; the limit is the guard against a loop.
MAX_DEFERRALS = 5


def _plan(
    user_id, kind: JobKind, *, subject_key: str, version: int, fire_at: datetime, context: Mapping[str, Any]
) -> ScheduledJob:
    with transaction.atomic():
        job, created = ScheduledJob.objects.select_for_update().get_or_create(
            user_id=user_id,
            kind=kind,
            subject_key=subject_key,
            expected_version=version,
            defaults={"fire_at": fire_at, "context": dict(context)},
        )
        if not created and job.status == JobStatus.PENDING and job.fire_at != fire_at:
            forget_message(job.external_id)
            job.fire_at, job.context, job.external_id = fire_at, dict(context), None
            job.save(update_fields=["fire_at", "context", "external_id", "updated_at"])
    if job.status == JobStatus.PENDING and job.external_id is None:
        publish(job)
    return job


def plan_timer_end(user_id, *, client_id, version: int, fire_at: datetime, context: Mapping[str, Any]) -> ScheduledJob:
    """The job that will tell the student their round (or break) ended, for this exact timer version."""
    return _plan(
        user_id, JobKind.TIMER_END, subject_key=str(client_id), version=version, fire_at=fire_at, context=context
    )


def plan_stopwatch_long(
    user_id, *, client_id, version: int, fire_at: datetime, context: Mapping[str, Any]
) -> ScheduledJob:
    """The job that will ask "still studying?" when this stopwatch version has counted long enough."""
    return _plan(
        user_id, JobKind.STOPWATCH_LONG, subject_key=str(client_id), version=version, fire_at=fire_at, context=context
    )


def plan_deferred(notification: Notification, deliver_at: datetime) -> ScheduledJob | None:
    """
    The send that waits for the end of quiet hours (FR-N33), or a send that is due now and must not run inside the
    student's request (a goal reached). One job per notification and moment: the same `deliver_at` returns the pending
    job, a new one (next version) is planned when the earlier job has already fired and found quiet hours still on.
    Returns None when the notification has been held `MAX_DEFERRALS` times already.
    """
    subject = str(notification.id)
    latest = (
        ScheduledJob.objects.filter(user_id=notification.user_id, kind=JobKind.DELIVER_DEFERRED, subject_key=subject)
        .order_by("-expected_version")
        .first()
    )
    if latest is None:
        version = 0
    elif latest.status == JobStatus.PENDING:
        version = latest.expected_version
    elif latest.expected_version + 1 >= MAX_DEFERRALS:
        log_event(logging.WARNING, "job_deferral_limit", event=notification.event)
        return None
    else:
        version = latest.expected_version + 1
    return _plan(
        notification.user_id,
        JobKind.DELIVER_DEFERRED,
        subject_key=subject,
        version=version,
        fire_at=deliver_at,
        context={"event": notification.event},
    )


def publish(job: ScheduledJob) -> None:
    try:
        external_id = queue.get_queue().publish(job.id, job.fire_at)
    except Exception as exc:  # noqa: BLE001 - the student's request must not fail; the sweep will fire the job
        log_event(logging.WARNING, "job_publish_failed", kind=job.kind, error_type=type(exc).__name__)
        return
    ScheduledJob.objects.filter(pk=job.pk, status=JobStatus.PENDING).update(
        external_id=external_id, updated_at=timezone.now()
    )
    job.external_id = external_id


def forget_message(external_id: str | None) -> None:
    if not external_id:
        return
    try:
        queue.get_queue().cancel(external_id)
    except Exception as exc:  # noqa: BLE001 - a courtesy only: a superseded job is skipped when it fires anyway
        log_event(logging.WARNING, "job_cancel_failed", error_type=type(exc).__name__)


def _cancel_pending(user_id, kind: JobKind, keep: tuple[object, int] | None) -> int:
    pending = ScheduledJob.objects.filter(user_id=user_id, kind=kind, status=JobStatus.PENDING)
    if keep is not None:
        pending = pending.exclude(subject_key=str(keep[0]), expected_version=keep[1])
    rows = list(pending.values_list("id", "external_id"))
    if not rows:
        return 0
    ids = [job_id for job_id, _ in rows]
    ScheduledJob.objects.filter(id__in=ids, status=JobStatus.PENDING).update(
        status=JobStatus.CANCELLED, updated_at=timezone.now()
    )
    for _, external_id in rows:
        forget_message(external_id)
    return len(rows)


def cancel_for_timer(user_id, *, keep: tuple[object, int] | None = None) -> int:
    """
    Cancel the student's pending timer jobs, except `keep` (client id and version of the one that stays). A new version
    supersedes the old one, and an ended, paused or discarded timer cancels everything. Returns how many were cancelled.
    """
    return _cancel_pending(user_id, JobKind.TIMER_END, keep)


def cancel_for_stopwatch(user_id, *, keep: tuple[object, int] | None = None) -> int:
    """The same for the student's pending long-stopwatch jobs."""
    return _cancel_pending(user_id, JobKind.STOPWATCH_LONG, keep)
