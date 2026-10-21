"""
Blueprint validation and hashing for F-08 Mock Tests.
"""

from __future__ import annotations

import hashlib
import json
from decimal import Decimal
from typing import Any


def compute_content_hash(items_data: list[dict[str, Any]]) -> str:
    """
    Computes SHA-256 of ordered (question_id, marks, section_key, group_key).
    Used for duplicate paper detection.
    """
    serialized = []
    for item in sorted(items_data, key=lambda x: x.get("position", 0)):
        q_id = str(item.get("question_id") or "")
        marks = str(Decimal(str(item.get("marks", 0))))
        sec_key = str(item.get("section_key") or "")
        grp_key = str(item.get("choice_group_key") or "")
        serialized.append(f"{q_id}:{marks}:{sec_key}:{grp_key}")

    raw = "|".join(serialized).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def validate_blueprint(
    sections: list[dict[str, Any]],
    items: list[dict[str, Any]],
    choice_groups: list[dict[str, Any]] | None = None,
    section_timing: str = "none",
) -> tuple[bool, list[str], Decimal]:
    """
    Validates blueprint according to FR-F08-01, FR-F08-03, FR-F08-04.
    Returns: (is_valid, list_of_problems, computed_total_marks)
    """
    problems: list[str] = []
    groups_by_key = {g.get("key"): g for g in (choice_groups or []) if g.get("key")}
    items_by_group: dict[str, list[dict[str, Any]]] = {}

    if not sections:
        problems.append("Paper must have at least one section.")

    if not items:
        problems.append("Paper must have at least one item.")

    # Check sections
    sec_keys = set()
    for sec in sections:
        skey = sec.get("key")
        if not skey:
            problems.append("Every section must have a key.")
        elif skey in sec_keys:
            problems.append(f"Duplicate section key: {skey}")
        sec_keys.add(skey)

        if section_timing == "sequential":
            dur = sec.get("duration_seconds")
            if not dur or dur <= 0:
                problems.append(f"Section {skey} must specify duration_seconds for sequential timing.")

    # Check items
    seen_positions = set()
    seen_questions = set()

    for item in items:
        pos = item.get("position")
        if pos is None or pos < 1:
            problems.append(f"Item display label {item.get('display_label', '')} has invalid position {pos}.")
        elif pos in seen_positions:
            problems.append(f"Duplicate position {pos} in items.")
        seen_positions.add(pos)

        q_id = item.get("question_id")
        if not q_id:
            problems.append(f"Item at position {pos} missing question_id.")
        elif q_id in seen_questions:
            problems.append(f"Duplicate question {q_id} in paper.")
        seen_questions.add(q_id)

        marks = Decimal(str(item.get("marks", 0)))
        if marks <= Decimal("0"):
            problems.append(f"Item at position {pos} must have positive marks.")

        grp_key = item.get("choice_group_key")
        if grp_key:
            if grp_key not in groups_by_key:
                problems.append(f"Item at position {pos} references unknown choice group '{grp_key}'.")
            else:
                items_by_group.setdefault(grp_key, []).append(item)

        sec_key = item.get("section_key")
        if sec_key and sec_key not in sec_keys:
            problems.append(f"Item at position {pos} references unknown section '{sec_key}'.")

    # Check choice groups
    for g_key, g in groups_by_key.items():
        g_items = items_by_group.get(g_key, [])
        req_count = g.get("required_count", 0)
        if req_count < 1:
            problems.append(f"Choice group '{g_key}' required_count must be at least 1.")
        if len(g_items) <= req_count:
            problems.append(
                f"Choice group '{g_key}' has {len(g_items)} items, must be > required_count ({req_count})."
            )

        # Equal marks check across group items
        marks_set = {Decimal(str(it.get("marks", 0))) for it in g_items}
        if len(marks_set) > 1:
            problems.append(f"Choice group '{g_key}' items must have equal marks.")

    # Calculate total counted marks
    # Regular items: sum their marks
    # Group items: required_count * marks_each
    total_marks = Decimal("0")
    counted_group_keys = set()

    for item in items:
        grp_key = item.get("choice_group_key")
        if not grp_key:
            total_marks += Decimal(str(item.get("marks", 0)))
        elif grp_key not in counted_group_keys:
            counted_group_keys.add(grp_key)
            g = groups_by_key.get(grp_key)
            if g and grp_key in items_by_group and items_by_group[grp_key]:
                req = g.get("required_count", 1)
                each_marks = Decimal(str(items_by_group[grp_key][0].get("marks", 0)))
                total_marks += Decimal(str(req)) * each_marks

    return len(problems) == 0, problems, total_marks
