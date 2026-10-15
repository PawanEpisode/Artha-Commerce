"""
Pure domain functions for marks validation and tree summation (F-09 ERD 3.5).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any


def validate_marks_tree(
    parts: list[dict[str, Any]],
    total_marks: Decimal,
    marks_note: str = "",
    choice_groups: list[dict[str, Any]] | None = None,
) -> list[str]:
    """
    Validates marks integrity for a paper:
    1. For every interior part with children, its marks must equal the sum of children marks.
    2. Sum of computable paper marks equals total_marks unless a marks_note explains the delta.
    """
    issues: list[str] = []

    # Map parts by number label or id
    part_children: dict[str, list[dict[str, Any]]] = {}
    top_level_parts: list[dict[str, Any]] = []

    for p in parts:
        parent_ref = p.get("parent_ref") or p.get("parent_id")
        if parent_ref:
            part_children.setdefault(str(parent_ref), []).append(p)
        else:
            top_level_parts.append(p)

    # 1. Interior parts marks check
    for p in parts:
        ref_key = str(p.get("id") or p.get("number_label"))
        children = part_children.get(ref_key, [])
        if children:
            expected = sum((Decimal(str(c.get("marks", 0))) for c in children), Decimal("0.00"))
            actual = Decimal(str(p.get("marks", 0)))
            if actual != expected:
                issues.append(
                    f"Part Q.{p.get('number_label')}: interior marks {actual} do not equal children sum {expected}"
                )

    # 2. Paper total calculation
    if choice_groups:
        calculated_total = Decimal("0.00")

        # Map top-level questions to choice groups
        for p in top_level_parts:
            cg_ref = p.get("choice_group_ref") or p.get("choice_group_id")
            if not cg_ref:
                # Compulsory standalone part
                calculated_total += Decimal(str(p.get("marks", 0)))

        for cg in choice_groups:
            identifiers = {str(cg.get("ref")), str(cg.get("id")), str(cg.get("label"))} - {"None", ""}
            cg_parts = [
                p for p in top_level_parts if str(p.get("choice_group_ref") or p.get("choice_group_id")) in identifiers
            ]
            rule = cg.get("rule_kind", "compulsory")
            pick_count = int(cg.get("pick_count", 1))

            if rule == "compulsory":
                calculated_total += sum((Decimal(str(p.get("marks", 0))) for p in cg_parts), Decimal("0.00"))
            else:
                # Average or uniform per-part marks * pick_count
                if cg_parts:
                    part_mark = Decimal(str(cg_parts[0].get("marks", 0)))
                    calculated_total += part_mark * pick_count

        if calculated_total != total_marks and not marks_note.strip():
            issues.append(
                f"Paper marks sum ({calculated_total}) does not match total_marks ({total_marks}) and no marks_note provided."
            )
    else:
        top_sum = sum((Decimal(str(p.get("marks", 0))) for p in top_level_parts), Decimal("0.00"))
        if top_sum != total_marks and not marks_note.strip():
            issues.append(
                f"Sum of top-level question marks ({top_sum}) does not match total_marks ({total_marks}) and no marks_note provided."
            )

    return issues
