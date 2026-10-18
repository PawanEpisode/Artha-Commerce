"""
Adapter for Practice Engine (F-06 practice module).
Isolated in an adapter so the domain and services do not import practice models directly.
"""

from __future__ import annotations

import uuid
from typing import Any

from modules.practice import services as practice_services
from modules.practice.models import AttemptAnswer, Session


def get_session(user_id: uuid.UUID, session_id: uuid.UUID) -> dict[str, Any] | None:
    """Loads session details by user and session id."""
    try:
        session = Session.objects.get(id=session_id, user_id=user_id, deleted_at__isnull=True)
    except Session.DoesNotExist:
        return None

    return {
        "id": session.id,
        "user_id": session.user_id,
        "mode": session.mode,
        "origin_module": session.origin_module,
        "origin_ref": session.origin_ref,
        "status": session.status,
        "local_date": session.local_date,
        "tz": session.tz,
        "submitted_at": session.submitted_at,
        "created_at": session.created_at,
    }


def get_session_answers(user_id: uuid.UUID, session_id: uuid.UUID) -> list[dict[str, Any]]:
    """Loads answer rows for a completed session."""
    answers = (
        AttemptAnswer.objects.filter(session_id=session_id, user_id=user_id)
        .order_by("position")
        .values(
            "position",
            "question_id",
            "question_version_id",
            "kind",
            "chapter_id",
            "subject_id",
            "status",
            "result",
            "marks_awarded",
            "marks_max",
            "grading_source",
            "time_spent_ms",
            "mistake_reason",
            "checked_at",
            "updated_at",
        )
    )

    # Compute frozen is_repeat (whether question was attempted prior to this session)
    question_ids = [a["question_id"] for a in answers if a.get("question_id")]
    prior_attempts: set[uuid.UUID] = set()
    if question_ids:
        earlier = (
            AttemptAnswer.objects.filter(
                user_id=user_id,
                question_id__in=question_ids,
            )
            .exclude(session_id=session_id)
            .values_list("question_id", flat=True)
            .distinct()
        )
        prior_attempts = set(earlier)

    res: list[dict[str, Any]] = []
    for a in answers:
        row = dict(a)
        row["is_repeat"] = a["question_id"] in prior_attempts
        res.append(row)

    return res


def create_fix_session(
    user_id: uuid.UUID,
    *,
    items: list[dict[str, Any]],
    client_id: uuid.UUID,
    tz: str = "Asia/Kolkata",
    title: str = "Fix Session",
    origin_ref: str = "",
) -> practice_services.SessionCreated:
    """Spawns an official practice session with origin 'analytics_fix'."""
    return practice_services.create_session_from_items(
        user_id=user_id,
        items=items,
        mode="revision",
        origin_module="analytics_fix",
        origin_ref=origin_ref,
        client_id=client_id,
        tz=tz,
        title=title,
        feedback_policy="instant",
        scoring_profile="practice",
        time_limit_seconds=None,
    )
