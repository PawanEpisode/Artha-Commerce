"""
Integrity classification and percentile eligibility for F-08 Mock Tests (ERD Section 3.5.7).
"""

from __future__ import annotations


def compute_integrity_class(
    *,
    section_scope: str | None,
    run_mode: str,
    time_extension_pct: int,
    attempt_no: int,
    replay_flagged: bool,
) -> str:
    """
    Computes attempt integrity class based on exam parameters.
    First match wins.
    """
    if section_scope is not None:
        return "section_scope"
    if run_mode == "relaxed":
        return "relaxed"
    if time_extension_pct > 0:
        return "extended"
    if attempt_no > 1:
        return "retake"
    if replay_flagged:
        return "replay_flagged"
    return "clean"


def is_percentile_eligible(
    *,
    integrity_class: str,
    share_anonymous: bool,
    paper_visibility: str,
    score_status: str,
) -> bool:
    """
    Checks if attempt qualifies to be included in anonymous percentile cohort.
    Only clean first attempts with explicit user consent on public/link papers.
    """
    if integrity_class != "clean":
        return False
    if not share_anonymous:
        return False
    if paper_visibility not in ("public", "link"):
        return False
    return True
