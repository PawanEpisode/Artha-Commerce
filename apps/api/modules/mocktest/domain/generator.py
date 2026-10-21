"""
Deterministic mock paper builder / generator algorithm (ERD Section 3.5.6).
"""

from __future__ import annotations

import hashlib
import random
from decimal import Decimal
from typing import Any

from ..errors import NotEnoughQuestions


def _item_hash(item_id: str, seed: str) -> str:
    return hashlib.md5(f"{item_id}:{seed}".encode()).hexdigest()


def fill_blueprint(
    *,
    target_marks: Decimal,
    chapter_weights: dict[str, float],
    candidates: list[dict[str, Any]],
    tolerance: Decimal = Decimal("2.0"),
    seed: str | int = "42",
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], Decimal]:
    """
    Deterministic fill algorithm.
    Returns: (selected_items, shortfalls, total_filled_marks)
    Raises: NotEnoughQuestions if total_filled_marks < 0.6 * target_marks
    """
    str_seed = str(seed)
    total_weight = sum(chapter_weights.values()) or 1.0

    # Sort candidates deterministically by pseudo-random seed hash
    sorted_candidates = sorted(candidates, key=lambda c: _item_hash(str(c["id"]), str_seed))

    # Group candidates by chapter
    by_chapter: dict[str, list[dict[str, Any]]] = {}
    for c in sorted_candidates:
        ch_id = str(c.get("chapter_id") or "")
        by_chapter.setdefault(ch_id, []).append(c)

    selected: list[dict[str, Any]] = []
    shortfalls: list[dict[str, Any]] = []
    total_filled = Decimal("0")

    # Allocate per chapter based on weight
    for ch_id, weight in chapter_weights.items():
        ch_target = (target_marks * Decimal(str(weight))) / Decimal(str(total_weight))
        ch_candidates = by_chapter.get(ch_id, [])

        ch_filled = Decimal("0")
        for cand in ch_candidates:
            c_marks = Decimal(str(cand.get("marks", 1)))
            if ch_filled + c_marks <= ch_target + tolerance:
                selected.append(cand)
                ch_filled += c_marks

        if ch_filled < ch_target - tolerance:
            shortfalls.append({
                "chapter_id": ch_id,
                "wanted_marks": float(ch_target),
                "got_marks": float(ch_filled),
            })
        total_filled += ch_filled

    # If any remaining marks budget, fill greedily from any remaining candidates
    if total_filled < target_marks - tolerance:
        selected_ids = {s["id"] for s in selected}
        remaining_candidates = [c for c in sorted_candidates if c["id"] not in selected_ids]
        for cand in remaining_candidates:
            c_marks = Decimal(str(cand.get("marks", 1)))
            if total_filled + c_marks <= target_marks + tolerance:
                selected.append(cand)
                total_filled += c_marks
            if total_filled >= target_marks - tolerance:
                break

    min_required = target_marks * Decimal("0.6")
    if total_filled < min_required:
        raise NotEnoughQuestions(
            message=f"Only {total_filled} marks available out of {target_marks} target (needs at least 60%).",
            shortfalls=shortfalls,
        )

    # Assign positions 1..len(selected)
    for idx, it in enumerate(selected, start=1):
        it["position"] = idx

    return selected, shortfalls, total_filled
