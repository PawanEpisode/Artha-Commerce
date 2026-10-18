"""
Pure aggregation and trend calculations for F-11.
Reference: PRD 6.1 and ERD 3.5.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal


@dataclass(frozen=True)
class SittingMark:
    term_code: str
    effective_marks: Decimal
    is_asked: bool


@dataclass(frozen=True)
class ChapterAggregateResult:
    papers_considered: int
    asked_n: int
    avg_effective: Decimal
    avg_when_asked: Decimal | None
    max_effective: Decimal | None
    last_asked_term_code: str | None
    trend: Decimal | None


def calculate_chapter_aggregates(
    sittings: list[SittingMark],
) -> ChapterAggregateResult:
    """
    Computes summary metrics and trend over an ordered list of sittings (newest first).
    """
    papers_considered = len(sittings)
    if papers_considered == 0:
        return ChapterAggregateResult(
            papers_considered=0,
            asked_n=0,
            avg_effective=Decimal("0.00"),
            avg_when_asked=None,
            max_effective=None,
            last_asked_term_code=None,
            trend=None,
        )

    asked_marks = [s.effective_marks for s in sittings if s.effective_marks > Decimal("0")]
    asked_n = len(asked_marks)
    total_effective = sum((s.effective_marks for s in sittings), Decimal("0"))

    avg_effective = (total_effective / Decimal(papers_considered)).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )

    avg_when_asked = None
    max_effective = None
    last_asked_term_code = None

    if asked_n > 0:
        avg_when_asked = (sum(asked_marks) / Decimal(asked_n)).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        max_effective = max(asked_marks)
        # Find newest sitting where asked
        for s in sittings:
            if s.effective_marks > Decimal("0"):
                last_asked_term_code = s.term_code
                break

    # Trend calculation (requires at least 5 sittings)
    trend: Decimal | None = None
    if papers_considered >= 5:
        # sittings are newest first: sittings[0..2] is last 3 sittings
        recent_3 = [float(s.effective_marks) for s in sittings[:3]]
        prev_3 = [float(s.effective_marks) for s in sittings[3:6]]  # up to 3 older

        mean_recent = sum(recent_3) / len(recent_3)
        mean_prev = sum(prev_3) / len(prev_3)
        mean_all = float(total_effective) / papers_considered

        denom = max(1.0, mean_all)
        r = (mean_recent - mean_prev) / denom
        r_clamped = max(-1.0, min(1.0, r))
        trend = Decimal(str(r_clamped)).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)

    return ChapterAggregateResult(
        papers_considered=papers_considered,
        asked_n=asked_n,
        avg_effective=avg_effective,
        avg_when_asked=avg_when_asked,
        max_effective=max_effective,
        last_asked_term_code=last_asked_term_code,
        trend=trend,
    )
