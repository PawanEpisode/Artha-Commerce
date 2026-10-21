"""
Progress and coverage calculations for F-12 Institute Study Material (PRD FR-F12-24, FR-F12-27).
"""

from __future__ import annotations

from typing import Any


def categorize_kind(kind: str) -> str:
    """
    Groups item kinds into primary buckets:
    - 'illustrations': illustration
    - 'examples': example
    - 'questions': exercise, mcq, true_false, theory, practical, case_study
    """
    if kind == "illustration":
        return "illustrations"
    if kind == "example":
        return "examples"
    return "questions"


def compute_chapter_summary(
    items: list[dict[str, Any]],
    progress_map: dict[str, dict[str, Any]],
    practice_done_item_ids: set[str] | None = None,
) -> dict[str, Any]:
    """
    Computes progress summary for a chapter's active items:
    items: list of dicts with:
      - 'id': str (editionitem id)
      - 'item_id': str (stable item id)
      - 'kind': str
      - 'match_hash': str | None
    progress_map: dict mapping item_id -> {
      - 'state': 'done' | 'revise' | 'skipped'
      - 'content_stamp': str | None
      - 'revisited_at': datetime | None
    }
    practice_done_item_ids: set of item_ids attempted in F-06 practice sessions.
    """
    practice_done = practice_done_item_ids or set()

    totals = {
        "total": len(items),
        "done": 0,
        "revise": 0,
        "skipped": 0,
        "todo": 0,
    }

    by_kind = {
        "illustrations": {"total": 0, "done": 0},
        "examples": {"total": 0, "done": 0},
        "questions": {"total": 0, "done": 0},
    }

    for it in items:
        item_id = str(it["item_id"])
        bucket = categorize_kind(it.get("kind", ""))
        by_kind[bucket]["total"] += 1

        prog = progress_map.get(item_id)
        state = prog.get("state") if prog else None

        # Check practice derived done
        is_done = (state == "done") or (item_id in practice_done)

        if is_done:
            totals["done"] += 1
            by_kind[bucket]["done"] += 1
        elif state == "revise":
            totals["revise"] += 1
        elif state == "skipped":
            totals["skipped"] += 1
        else:
            totals["todo"] += 1

    tot = totals["total"]
    percent = round(100.0 * totals["done"] / tot) if tot > 0 else 0

    return {
        "total": tot,
        "done": totals["done"],
        "revise": totals["revise"],
        "skipped": totals["skipped"],
        "todo": totals["todo"],
        "percent": percent,
        "by_kind": by_kind,
    }


def is_revised_since_done(
    progress_entry: dict[str, Any] | None,
    current_match_hash: str | None,
) -> bool:
    """
    Returns True if an item was previously marked done, but the content stamp
    has changed in the new edition and the student hasn't revisited it yet.
    """
    if not progress_entry or not current_match_hash:
        return False

    if progress_entry.get("state") != "done":
        return False

    if progress_entry.get("revisited_at") is not None:
        return False

    stamp = progress_entry.get("content_stamp")
    if not stamp:
        return False

    return stamp != current_match_hash
