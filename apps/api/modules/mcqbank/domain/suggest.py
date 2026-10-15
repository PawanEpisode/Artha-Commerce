"""
Quick set suggestion domain logic (F-05 ERD 3.5).
Ranks chapters to suggest the next high-yield practice set.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class ChapterMetrics:
    chapter_id: str
    subject_key: str
    chapter_key: str
    available: int
    wrong_last: int
    due: int
    unseen: int
    coverage_pct: float
    practised_last_24h: bool
    syllabus_order: int


@dataclass(frozen=True)
class ScoredSuggestion:
    chapter_id: str
    subject_key: str
    chapter_key: str
    score: float
    reasons: list[str]


def score_chapter(m: ChapterMetrics) -> ScoredSuggestion:
    """Computes suggestion score and contributing reasons for one chapter."""
    w_term = 0.40 * min(1.0, m.wrong_last / 5.0)
    d_term = 0.25 * min(1.0, m.due / 5.0)
    u_term = 0.20 * min(1.0, m.unseen / 10.0)
    cov_term = 0.15 * (1.0 - (m.coverage_pct / 100.0))
    recency_penalty = 0.30 if m.practised_last_24h else 0.0

    score = w_term + d_term + u_term + cov_term - recency_penalty

    reasons: list[str] = []
    if w_term >= 0.10:
        reasons.append("wrong_last")
    if d_term >= 0.10:
        reasons.append("due")
    if u_term >= 0.10:
        reasons.append("unseen")
    if cov_term >= 0.10:
        reasons.append("low_coverage")

    if not reasons:
        reasons.append("unseen" if m.unseen > 0 else "low_coverage")

    return ScoredSuggestion(
        chapter_id=m.chapter_id,
        subject_key=m.subject_key,
        chapter_key=m.chapter_key,
        score=score,
        reasons=reasons,
    )


def rank_suggestions(candidates: Sequence[ChapterMetrics]) -> ScoredSuggestion | None:
    """
    Ranks chapter candidates and returns top suggestion.
    Asserts available >= 5; falls back to first_time on tie/cold start.
    """
    valid = [c for c in candidates if c.available >= 5]
    if not valid:
        if not candidates:
            return None
        # Cold start fallback
        first = sorted(candidates, key=lambda c: (c.coverage_pct, c.syllabus_order))[0]
        return ScoredSuggestion(
            chapter_id=first.chapter_id,
            subject_key=first.subject_key,
            chapter_key=first.chapter_key,
            score=0.0,
            reasons=["first_time"],
        )

    scored = [score_chapter(c) for c in valid]
    # Sort key: (-score, syllabus_order)
    order_map = {c.chapter_id: c.syllabus_order for c in valid}
    scored.sort(key=lambda s: (-s.score, order_map.get(s.chapter_id, 0)))
    return scored[0]
