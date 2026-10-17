"""
Owner overrides for PYQ seeds: `seed/cma-final/pyq-overrides/<paper>-<term>.json`, schema `artha.qboverride.v1`.

The owner sometimes fixes a part directly in the generated seed JSON. A rebuild would silently throw that away, so each such
edit is kept here, keyed by part ref, and `apply_overrides` lays it back over the freshly built payload as the very last step.
Only the listed fields change. The paper's `answers_status` and the draft report are recomputed afterwards.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

SCHEMA = "artha.qboverride.v1"
FIELDS = {
    "stem_md",
    "options",
    "kind",
    "explanation_md",
    "reference_solution_md",
    "publish",
    "answer_source",
    "difficulty",
    "mapping_state",
    "mapping_confidence",
    "chapter_key",
}


def load_overrides_file(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema") != SCHEMA:
        raise ValueError(f"{path.name}: expected schema {SCHEMA}")
    parts = data.get("parts") or {}
    for ref, fields in parts.items():
        unknown = set(fields) - FIELDS
        if unknown:
            raise ValueError(f"{path.name} {ref}: unknown override fields {sorted(unknown)}")
    return parts


def recompute_answers_status(payload: dict[str, Any]) -> str:
    leaves = [p for p in payload["parts"] if p.get("is_leaf")]
    answered = 0
    for leaf in leaves:
        if leaf.get("kind", "").startswith("mcq"):
            if any(o.get("is_correct") for o in leaf.get("options", [])):
                answered += 1
        elif leaf.get("answer_source") and (leaf.get("explanation_md") or "").strip():
            answered += 1
    if answered == 0:
        return "none"
    return "complete" if answered == len(leaves) else "partial"


def apply_overrides(result: dict[str, Any], overrides: dict[str, dict[str, Any]]) -> list[str]:
    """Mutates a `pyq.build_paper` result; returns the part labels that were overridden."""
    if not overrides:
        return []
    by_ref = {p["ref"]: p for p in result["payload"]["parts"]}
    applied: list[str] = []
    for ref, fields in overrides.items():
        leaf = by_ref.get(ref)
        if leaf is None or not fields:
            continue
        leaf.update(fields)
        applied.append(ref)
    published = {ref for ref in applied if by_ref[ref].get("publish")}
    result["report"] = [r for r in result["report"] if r["part"] not in published]
    result["counts"]["draft_parts"] = len(result["report"])
    result["payload"]["answers_status"] = (
        recompute_answers_status(result["payload"]) if applied else result["payload"]["answers_status"]
    )
    result["overrides"] = applied
    return applied
