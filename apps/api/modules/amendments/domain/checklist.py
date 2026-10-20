from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ChecklistResult:
    is_valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def check_word_overlap(text1: str, text2: str, max_run: int = 20) -> str | None:
    """
    Checks if text1 and text2 share a consecutive run of `max_run` or more normalized words.
    Returns the matching phrase if found, or None.
    """
    if not text1 or not text2:
        return None

    def tokenize(text: str) -> list[str]:
        return re.findall(r"\b\w+\b", text.lower())

    words1 = tokenize(text1)
    words2 = tokenize(text2)

    if len(words1) < max_run or len(words2) < max_run:
        return None

    words2_set = set()
    for j in range(len(words2) - max_run + 1):
        words2_set.add(" ".join(words2[j : j + max_run]))

    for i in range(len(words1) - max_run + 1):
        run = " ".join(words1[i : i + max_run])
        if run in words2_set:
            return run

    return None


def validate_revision_release(
    state: str,
    subject_count: int,
    term_count: int,
    change_versions: list[dict[str, Any]],
    official_url: str = "",
) -> ChecklistResult:
    """
    Validates whether a document revision meets the criteria for atomic release (PRD FR-F14-09).
    """
    errors: list[str] = []
    warnings: list[str] = []

    # 1. State must be staged or in_review
    if state not in ("staged", "in_review"):
        errors.append(f"Revision state must be 'staged' or 'in_review' to release, got '{state}'.")

    # 2. Paper scope (at least 1 paper/subject)
    if subject_count < 1:
        errors.append("At least one syllabus paper must be linked to the revision scope.")

    # 3. Term applicability (at least 1 exam term row)
    if term_count < 1:
        errors.append("At least one exam term applicability row must be defined.")

    # 4. Changes present
    if not change_versions:
        warnings.append("Revision contains no change cards.")

    # 5. Check mapping for each card
    for idx, cv in enumerate(change_versions, 1):
        change_type = cv.get("change_type", "")
        has_mapping = cv.get("has_mapping", False)
        title = cv.get("title") or cv.get("provision_label") or f"Card #{idx}"

        if change_type != "clarification" and not has_mapping:
            errors.append(f"Card '{title}' must be mapped to at least one paper/chapter.")

        # Check word overlap with evidence quote (copyright guard)
        evidence = cv.get("evidence_quote", "")
        summary_new = cv.get("summary_new", "")
        summary_old = cv.get("summary_old", "")

        overlap_new = check_word_overlap(summary_new, evidence, max_run=20)
        if overlap_new:
            warnings.append(
                f"Card '{title}' summary shares a 20+ word verbatim run with evidence quote: '{overlap_new[:50]}...'"
            )

        overlap_old = check_word_overlap(summary_old, evidence, max_run=20)
        if overlap_old:
            warnings.append(
                f"Card '{title}' old summary shares a 20+ word verbatim run with evidence quote: '{overlap_old[:50]}...'"
            )

    # 6. Official URL should be present for verification
    if not official_url:
        warnings.append("Official PDF source URL is missing.")

    return ChecklistResult(
        is_valid=len(errors) == 0,
        errors=errors,
        warnings=warnings,
    )
