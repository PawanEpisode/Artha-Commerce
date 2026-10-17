"""
Workbook supplements: `seed/cma-final/workbook-supplement/<paper>.json`, schema `artha.qbsupplement.v1`.

The workbook parser cuts the PDF at each printed "ILLUSTRATION" heading, and now and then a printed layout does not fit that
cut: an illustration with no solution of its own whose answer sits under the next one (merge), or an illustration the cut
swallowed (insert). A supplement states those decisions once, from the page images, and `apply_supplement` lays them over the
parsed items as the last build step. Applying it twice changes nothing.

    {"schema": "artha.qbsupplement.v1", "paper": "p19",
     "merge":  [{"into": ref, "from": ref, "note": "..."}],
     "insert": [{"after": ref, "item": {...a complete item...}}],
     "patch":  [{"ref": ref, "evidence": {...merged into evidence...}, "drop_typeset_notes_containing": "text"}]}
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

SCHEMA = "artha.qbsupplement.v1"


def load_supplement_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema") != SCHEMA:
        raise ValueError(f"{path.name}: expected schema {SCHEMA}")
    return data


def _index(items: list[dict[str, Any]], ref: str) -> int:
    for i, item in enumerate(items):
        if item["external_ref"] == ref:
            return i
    return -1


def apply_supplement(items: list[dict[str, Any]], supplement: dict[str, Any]) -> list[str]:
    """Mutates `items`; returns a log of what changed (empty when everything was already applied)."""
    log: list[str] = []
    for op in supplement.get("merge", []):
        src = _index(items, op["from"])
        dst = _index(items, op["into"])
        if src < 0 or dst < 0:
            continue
        into, other = items[dst], items[src]
        a, b = into["payload"], other["payload"]
        a["stem_md"] = a["stem_md"].rstrip() + "\n\n" + b["stem_md"].lstrip()
        for key in ("explanation_md",):
            if not (a.get(key) or "").strip():
                a[key] = b.get(key, "")
        if not (a["rubric"].get("reference_solution_md") or "").strip():
            a["rubric"]["reference_solution_md"] = b["rubric"].get("reference_solution_md", "")
        into["review_reasons"] = []
        into["status"] = "ok"
        into["evidence"].setdefault("merged_from", []).append(op["from"])
        into["evidence"]["typeset_notes"] = list(into["evidence"].get("typeset_notes", [])) + [op["note"]]
        into["evidence"]["review"] = {
            "verdict": "approve",
            "reason": op["note"],
            "fixes": [f"Merged {op['from']} into this item"],
            "printed_issues": op.get("printed_issues", []),
            "by": "owner-decision",
        }
        del items[src]
        log.append(f"merged {op['from']} into {op['into']}")
    for op in supplement.get("insert", []):
        item = op["item"]
        if _index(items, item["external_ref"]) >= 0:
            continue
        at = _index(items, op["after"])
        if at < 0:
            raise ValueError(f"insert: no item {op['after']}")
        items.insert(at + 1, copy.deepcopy(item))
        log.append(f"inserted {item['external_ref']}")
    for op in supplement.get("patch", []):
        at = _index(items, op["ref"])
        if at < 0:
            continue
        ev = items[at]["evidence"]
        before = json.dumps(ev, sort_keys=True)
        ev.update(op.get("evidence", {}))
        needle = op.get("drop_typeset_notes_containing")
        if needle:
            ev["typeset_notes"] = [n for n in ev.get("typeset_notes", []) if needle not in n]
        if json.dumps(ev, sort_keys=True) != before:
            log.append(f"patched {op['ref']}")
    return log


def recount(seed: dict[str, Any]) -> None:
    items = seed["items"]
    ok = sum(1 for i in items if i["status"] == "ok")
    seed["counts"] = {**seed.get("counts", {}), "items": len(items), "ok": ok, "needs_review": len(items) - ok}
