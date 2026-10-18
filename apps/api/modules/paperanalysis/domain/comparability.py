"""
Scheme comparability and history-carrying rules for F-11.
Reference: ERD 3.5.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from modules.syllabus.selectors import MapEdge


class ComparabilityStatus:
    NATIVE = "native"
    CARRIED = "carried"
    RESTRUCTURED = "restructured"
    NEW = "new"


@dataclass(frozen=True)
class PaperComparability:
    status: str  # "native" | "carried" | "restructured" | "not_applicable"
    source_chapter_ids: list[UUID]
    carry_weight: float


def evaluate_comparability(
    current_chapter_id: UUID,
    current_scheme_id: UUID,
    paper_scheme_id: UUID,
    edges_into_chapter: list[MapEdge],
    default_carry_weight: float = 0.7,
) -> PaperComparability:
    """
    Evaluates comparability of a paper in `paper_scheme_id` against `current_chapter_id`
    in `current_scheme_id`.
    """
    if current_scheme_id == paper_scheme_id:
        return PaperComparability(
            status=ComparabilityStatus.NATIVE,
            source_chapter_ids=[current_chapter_id],
            carry_weight=1.0,
        )

    # Filter edges from paper_scheme_id into current_chapter_id
    relevant_edges = [
        e for e in edges_into_chapter
        if e.to_chapter_id == current_chapter_id
    ]

    if not relevant_edges:
        # Chapter did not exist in this older scheme
        return PaperComparability(
            status="not_applicable",
            source_chapter_ids=[],
            carry_weight=0.0,
        )

    # Any split, partial, or needs_review edge makes it restructured
    if any(e.needs_review or e.relation in ("split", "partial") for e in relevant_edges):
        return PaperComparability(
            status=ComparabilityStatus.RESTRUCTURED,
            source_chapter_ids=[],
            carry_weight=0.0,
        )

    # All edges are 'same' or 'merged' and not needs_review
    # This is carried history
    source_ids = [e.from_chapter_id for e in relevant_edges]
    # For carried history, apply carry weight (default 0.7)
    return PaperComparability(
        status=ComparabilityStatus.CARRIED,
        source_chapter_ids=source_ids,
        carry_weight=default_carry_weight,
    )
