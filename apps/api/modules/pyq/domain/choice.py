"""
Choice rules domain logic for past papers (F-09 ERD 3.5).
"""

from __future__ import annotations

from typing import Any


def validate_choice_groups(
    choice_groups: list[dict[str, Any]],
    top_level_parts: list[dict[str, Any]],
) -> list[str]:
    """
    Validates choice rules:
    - compulsory requires pick_count == of_count.
    - any_n_of_m or either_or requires pick_count < of_count.
    - of_count must equal the number of top-level questions associated with the choice group.
    """
    issues: list[str] = []

    for cg in choice_groups:
        identifiers = {str(cg.get("ref")), str(cg.get("id")), str(cg.get("label"))} - {"None", ""}
        rule_kind = cg.get("rule_kind", "compulsory")
        pick_count = int(cg.get("pick_count", 1))
        of_count = int(cg.get("of_count", 1))

        if rule_kind == "compulsory" and pick_count != of_count:
            issues.append(f"Choice group '{cg.get('label')}': compulsory rule requires pick_count == of_count.")

        if rule_kind in ("any_n_of_m", "either_or") and pick_count >= of_count:
            issues.append(
                f"Choice group '{cg.get('label')}': {rule_kind} requires pick_count ({pick_count}) < of_count ({of_count})."
            )

        linked_parts = [
            p for p in top_level_parts if str(p.get("choice_group_ref") or p.get("choice_group_id")) in identifiers
        ]

        if len(linked_parts) != of_count:
            issues.append(
                f"Choice group '{cg.get('label')}': of_count is {of_count} but {len(linked_parts)} parts reference it."
            )

    return issues
