"""
Domain events for MCQ Bank (F-05 ERD 3.3).
Emits through the synchronous core.events bus with strict JSON schema payload.
"""

from __future__ import annotations

import uuid

from core import events


def emit_set_published(
    set_id: uuid.UUID,
    slug: str,
    delivery: str,
    subject_key: str,
    chapter_ids: list[uuid.UUID],
    term_code: str,
    question_count: int | None,
) -> None:
    events.emit(
        "mcq_set_published",
        payload={
            "set_id": str(set_id),
            "slug": slug,
            "delivery": delivery,
            "subject_key": subject_key,
            "chapter_ids": [str(cid) for cid in chapter_ids],
            "term_code": term_code,
            "question_count": question_count,
        },
        key=str(set_id),
    )


def emit_set_withdrawn(set_id: uuid.UUID, reason: str, open_sessions: int = 0) -> None:
    events.emit(
        "mcq_set_withdrawn",
        payload={
            "set_id": str(set_id),
            "reason": reason,
            "open_sessions": open_sessions,
        },
        key=str(set_id),
    )


def emit_external_logged(
    user_id: uuid.UUID,
    set_id: uuid.UUID,
    chapter_id: uuid.UUID | None,
    score_pct: float,
) -> None:
    events.emit(
        "mcq_external_logged",
        payload={
            "set_id": str(set_id),
            "chapter_id": str(chapter_id) if chapter_id else None,
            "score_pct": score_pct,
        },
        user_id=user_id,
        key=str(set_id),
    )


def emit_adaptive_round_applied(
    user_id: uuid.UUID,
    run_id: uuid.UUID,
    scope_type: str,
    theta_before: float,
    theta_after: float,
) -> None:
    events.emit(
        "mcq_adaptive_round_applied",
        payload={
            "run_id": str(run_id),
            "scope_type": scope_type,
            "theta_before": theta_before,
            "theta_after": theta_after,
        },
        user_id=user_id,
        key=str(run_id),
    )
