"""
Matching algorithm for F-12 Institute Study Material (ERD 3.2).
Pure deterministic functions comparing items between two editions.
"""

from __future__ import annotations

import difflib
from dataclasses import dataclass
from typing import Any


MATERIAL_MATCH_AUTO = 0.85
MATERIAL_MATCH_MIN = 0.55


@dataclass
class MatchCandidate:
    item_id: str | None
    previous_row_id: str | None
    new_row_temp_id: str
    change_kind: str  # 'same', 'edited', 'renumbered', 'moved', 'new', 'removed'
    match_method: str  # 'hash', 'label', 'alignment', 'fuzzy', 'manual', 'new'
    match_confidence: float
    match_status: str  # 'auto', 'needs_review', 'confirmed'


def descriptor_similarity(d1: str | None, d2: str | None) -> float:
    """Computes string similarity between two descriptors."""
    s1 = (d1 or "").strip().lower()
    s2 = (d2 or "").strip().lower()
    if not s1 and not s2:
        return 1.0
    if not s1 or not s2:
        return 0.0
    return difflib.SequenceMatcher(None, s1, s2).ratio()


def match_units_items(
    previous_rows: list[dict[str, Any]],
    new_rows: list[dict[str, Any]],
    *,
    auto_threshold: float = MATERIAL_MATCH_AUTO,
    min_threshold: float = MATERIAL_MATCH_MIN,
) -> list[MatchCandidate]:
    """
    Matches items of a new edition against a previous edition within a unit.
    Each row dict should contain:
      - 'id': str
      - 'item_id': str (for previous rows)
      - 'kind': str
      - 'label_norm': str
      - 'match_hash': str | None
      - 'descriptor': str | None
      - 'position': int
    """
    results: list[MatchCandidate] = []
    unmatched_prev = {r["id"]: r for r in previous_rows}
    unmatched_new = {r["id"]: r for r in new_rows}

    # Step 1: Exact match on match_hash within same kind
    matched_new_ids = set()
    for n_id, n_row in list(unmatched_new.items()):
        n_hash = n_row.get("match_hash")
        n_kind = n_row.get("kind")
        if not n_hash:
            continue

        for p_id, p_row in list(unmatched_prev.items()):
            if p_row.get("kind") == n_kind and p_row.get("match_hash") == n_hash:
                change = "same" if p_row.get("label_norm") == n_row.get("label_norm") else "renumbered"
                results.append(
                    MatchCandidate(
                        item_id=p_row.get("item_id"),
                        previous_row_id=p_id,
                        new_row_temp_id=n_id,
                        change_kind=change,
                        match_method="hash",
                        match_confidence=1.0,
                        match_status="auto",
                    )
                )
                unmatched_prev.pop(p_id)
                matched_new_ids.add(n_id)
                break

    for n_id in matched_new_ids:
        unmatched_new.pop(n_id, None)

    # Step 2: Match on same kind and equal label_norm
    matched_new_ids.clear()
    for n_id, n_row in list(unmatched_new.items()):
        n_label = n_row.get("label_norm")
        n_kind = n_row.get("kind")

        for p_id, p_row in list(unmatched_prev.items()):
            if p_row.get("kind") == n_kind and p_row.get("label_norm") == n_label:
                sim = descriptor_similarity(p_row.get("descriptor"), n_row.get("descriptor"))
                if sim >= 0.6:
                    change = "same" if sim > 0.95 else "edited"
                    conf = 0.90 if sim > 0.8 else 0.75
                    status = "auto" if conf >= auto_threshold else "needs_review"
                    results.append(
                        MatchCandidate(
                            item_id=p_row.get("item_id"),
                            previous_row_id=p_id,
                            new_row_temp_id=n_id,
                            change_kind=change,
                            match_method="label",
                            match_confidence=conf,
                            match_status=status,
                        )
                    )
                    unmatched_prev.pop(p_id)
                    matched_new_ids.add(n_id)
                    break

    for n_id in matched_new_ids:
        unmatched_new.pop(n_id, None)

    # Step 3: Positional sequence alignment on remaining same-kind rows
    kinds = set(r.get("kind") for r in unmatched_new.values())
    for k in kinds:
        k_prev = sorted([r for r in unmatched_prev.values() if r.get("kind") == k], key=lambda x: x.get("position", 0))
        k_new = sorted([r for r in unmatched_new.values() if r.get("kind") == k], key=lambda x: x.get("position", 0))

        # Compare pair by pair if lists match in relative sequence
        for n_row in k_new:
            best_match = None
            best_sim = 0.0

            for p_row in k_prev:
                sim = descriptor_similarity(p_row.get("descriptor"), n_row.get("descriptor"))
                if sim > best_sim:
                    best_sim = sim
                    best_match = p_row

            if best_match and best_sim >= 0.75:
                conf = round(0.9 * best_sim, 2)
                change = "renumbered" if best_match.get("label_norm") != n_row.get("label_norm") else "edited"
                status = "auto" if conf >= auto_threshold else "needs_review"

                results.append(
                    MatchCandidate(
                        item_id=best_match.get("item_id"),
                        previous_row_id=best_match["id"],
                        new_row_temp_id=n_row["id"],
                        change_kind=change,
                        match_method="alignment",
                        match_confidence=conf,
                        match_status=status,
                    )
                )
                k_prev.remove(best_match)
                unmatched_prev.pop(best_match["id"], None)
                unmatched_new.pop(n_row["id"], None)

    # Step 4: Leftover new rows -> 'new'
    for n_id, n_row in unmatched_new.items():
        results.append(
            MatchCandidate(
                item_id=None,  # will generate new item identity
                previous_row_id=None,
                new_row_temp_id=n_id,
                change_kind="new",
                match_method="new",
                match_confidence=1.0,
                match_status="auto",
            )
        )

    # Step 5: Leftover previous rows -> 'removed' tombstones
    for p_id, p_row in unmatched_prev.items():
        results.append(
            MatchCandidate(
                item_id=p_row.get("item_id"),
                previous_row_id=p_id,
                new_row_temp_id="",
                change_kind="removed",
                match_method="new",
                match_confidence=1.0,
                match_status="auto",
            )
        )

    return results
