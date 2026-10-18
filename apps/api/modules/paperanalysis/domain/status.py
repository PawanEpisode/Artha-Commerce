"""
Data status determination for F-11.
Reference: ERD 3.5.
"""

from __future__ import annotations


class DataStatus:
    INSUFFICIENT = "insufficient"
    LIMITED = "limited"
    READY = "ready"
    WITHHELD = "withheld"


def determine_data_status(
    papers_published: int,
    exam_papers_published: int,
    has_limited_paper: bool = False,
    backtest_lift: float | None = None,
    min_backtest_lift: float = 1.15,
    min_papers_to_rank: int = 4,
    admin_withheld: bool = False,
) -> tuple[str, str | None]:
    """
    Determines subject data status and optional withheld reason.
    Returns (status, withheld_reason).
    """
    if admin_withheld:
        return DataStatus.WITHHELD, "editor_override"

    # Withheld rule: at least 6 exam papers and back-test lift below threshold
    if exam_papers_published >= 6 and backtest_lift is not None:
        if backtest_lift < min_backtest_lift:
            return DataStatus.WITHHELD, "backtest_below_threshold"

    # Insufficient: fewer than 4 papers published
    if papers_published < min_papers_to_rank:
        return DataStatus.INSUFFICIENT, None

    # Limited: 4 to 5 papers, or no exam papers (practice only), or contains a limited paper
    if papers_published <= 5 or exam_papers_published == 0 or has_limited_paper:
        return DataStatus.LIMITED, None

    return DataStatus.READY, None
