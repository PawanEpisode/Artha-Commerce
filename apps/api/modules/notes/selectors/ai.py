"""Reads of AI jobs (R3). Always scoped to the student; a job that is not theirs is simply absent."""

from __future__ import annotations

from ..models import AiJob


def get_job(user_id, job_id) -> AiJob | None:
    return AiJob.objects.filter(pk=job_id, user_id=user_id).first()


def latest_for_chapter(user_id, chapter_id, kind: str = AiJob.Kind.EXAM_SUMMARY) -> AiJob | None:
    """The newest job of the chapter that still matters to the student: running, or a draft waiting for review."""
    return (
        AiJob.objects.filter(
            user_id=user_id, kind=kind, scope__chapter_id=str(chapter_id), status__in=["queued", "running", "ready"]
        )
        .order_by("-created_at")
        .first()
    )
