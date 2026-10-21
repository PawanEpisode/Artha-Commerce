"""
Registrations for F-08 Mock Tests and MTP.
"""

from __future__ import annotations

import uuid
from typing import Any

from modules.practice.registry import (
    OriginSpec,
    PickContext,
    PickedItem,
    register_origin,
    register_picker,
)


def pick_mock_blueprint(ctx: PickContext) -> list[PickedItem]:
    """
    Practice picker for mock blueprint sets.
    """
    from .domain import generator
    from modules.questionbank.models import Question
    from modules.questionbank.selectors import search_ids

    spec = ctx.spec
    chapter_ids = spec.get("chapter_ids", [])
    target_marks = spec.get("marks", 20)
    weights = {str(cid): 1.0 for cid in chapter_ids}

    q_ids = search_ids(
        viewer_id=ctx.user_id,
        flt={"chapter_ids": [uuid.UUID(cid) for cid in chapter_ids if cid]},
        limit=100,
    )
    candidates = []
    for q in Question.objects.filter(id__in=q_ids).select_related("published_version"):
        v = q.published_version
        if v:
            candidates.append({
                "id": str(q.id),
                "chapter_id": str(chapter_ids[0]) if chapter_ids else "",
                "marks": v.marks or 1.0,
            })

    try:
        selected, _, _ = generator.fill_blueprint(
            target_marks=target_marks,
            chapter_weights=weights,
            candidates=candidates,
            seed=spec.get("seed", 42),
        )
    except Exception:
        selected = candidates[:ctx.limit]

    return [PickedItem(question_id=uuid.UUID(s["id"])) for s in selected]


def live_mock_timer_provider(user_id: uuid.UUID) -> str | None:
    """
    Returns description string while student is taking an active mock exam.
    Prevents starting pomodoro / stopwatch simultaneously.
    """
    from .models import Attempt

    live_attempt = Attempt.objects.filter(
        user_id=user_id,
        phase__in=[Attempt.Phase.READING, Attempt.Phase.WRITING, Attempt.Phase.UPLOAD],
        deleted_at__isnull=True,
    ).select_related("paper").first()

    if live_attempt:
        return f"Mock Exam in progress: {live_attempt.paper.title}"
    return None


def register_mocktest_origins_and_pickers() -> None:
    register_origin(
        "mtp",
        OriginSpec(
            allowed_modes={"exam", "timed"},
            default_feedback_policy="at_end",
            unique_per_user=False,
        ),
    )
    register_origin(
        "mock",
        OriginSpec(
            allowed_modes={"exam", "timed"},
            default_feedback_policy="at_end",
            unique_per_user=False,
        ),
    )
    register_picker(
        "mock_blueprint",
        pick_mock_blueprint,
        description="Picks questions fulfilling blueprint structure and chapter weights",
    )
