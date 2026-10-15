"""
Practice pickers and origin registrations for PYQ (F-09 ERD 3.2, 3.6).
"""

from __future__ import annotations

from modules.practice.registry import (
    OriginSpec,
    PickContext,
    PickedItem,
    register_origin,
    register_picker,
)

from .models import PaperQuestion


def pick_pyq_paper(ctx: PickContext) -> list[PickedItem]:
    """Picks all leaf items of a paper in printed sort order with frozen marks."""
    paper_id = ctx.spec.get("paper_id")
    if not paper_id:
        return []

    pqs = (
        PaperQuestion.objects.filter(paper_id=paper_id, is_leaf=True, question__isnull=False)
        .order_by("sort_order")
        .select_related("choice_group")
    )
    return [
        PickedItem(
            question_id=pq.question_id,
            marks=pq.marks,
            section_label=pq.choice_group.section_label if pq.choice_group else None,
        )
        for pq in pqs
    ]


def pick_pyq_ranked(ctx: PickContext) -> list[PickedItem]:
    """Picks past paper questions for a chapter ranked by term recency."""
    chapter_id = ctx.spec.get("chapter_id")
    if not chapter_id:
        return []

    pqs = (
        PaperQuestion.objects.filter(
            chapter_id=chapter_id,
            is_leaf=True,
            question__isnull=False,
            paper__status="published",
        )
        .order_by("-paper__term_code", "sort_order")
        .select_related("choice_group")[: ctx.limit]
    )
    return [
        PickedItem(
            question_id=pq.question_id,
            marks=pq.marks,
            section_label=pq.choice_group.section_label if pq.choice_group else None,
        )
        for pq in pqs
    ]


def register_pyq_pickers_and_origins() -> None:
    register_picker(
        "pyq_paper",
        pick_pyq_paper,
        description="Picks all questions of a past paper in sequence",
    )
    register_picker(
        "pyq_ranked",
        pick_pyq_ranked,
        description="Picks chapter past questions ordered by recency",
    )
    register_origin(
        "pyq",
        OriginSpec(
            allowed_modes={"untimed", "timed", "chapter_quiz", "exam"},
            default_feedback_policy="at_end",
            unique_per_user=False,
        ),
    )
    register_origin(
        "pyq_daily",
        OriginSpec(
            allowed_modes={"timed"},
            default_feedback_policy="at_end",
            unique_per_user=True,
        ),
    )
