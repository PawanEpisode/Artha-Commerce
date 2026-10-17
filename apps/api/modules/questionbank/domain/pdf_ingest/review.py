"""
Review decisions (`artha.qbreview.v1`): the outcome of comparing a draft item with the printed page, recorded per item.

A decision can correct the stored text (only the transcription, never the Institute's wording), settle a numeric key,
and approve the item for publishing or hold it. Pure; the build command reads the files and `seedbuild` applies them.
Corrected text goes through the same cleaning and hard gates as the typeset overlay, so a decision can never put text in
a seed that the editor lint or KaTeX would reject.
"""

from __future__ import annotations

import json
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from core import richtext

from . import typeset

SCHEMA = "artha.qbreview.v1"
REVIEWER = "claude-review"


def load_decisions(folder: Path, paper: str) -> dict[str, dict[str, Any]]:
    path = folder / f"p{paper.lower()}.json"
    if not path.exists():
        return {}
    doc = json.loads(path.read_text(encoding="utf-8"))
    if doc.get("schema") != SCHEMA:
        raise ValueError(f"{path.name}: expected schema {SCHEMA}")
    return doc.get("items", {})


def load_decisions_file(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    doc = json.loads(path.read_text(encoding="utf-8"))
    if doc.get("schema") != SCHEMA:
        raise ValueError(f"{path.name}: expected schema {SCHEMA}")
    return doc.get("items", {})


def _checked(md: str, *, check: bool) -> tuple[str, list[str]]:
    """Cleaned text and the hard-gate errors for it (empty list when it may be used)."""
    cleaned = typeset._clean(md)
    errors = [i.message for i in richtext.errors_of(richtext.lint(cleaned, richtext.QUESTION))]
    if check:
        fs = typeset.formulas_of(cleaned)
        res = typeset.katex_errors(fs)
        if res:
            errors += [f"KaTeX cannot render `{f.tex[:50]}`: {e}" for f, e in zip(fs, res, strict=True) if e]
    return cleaned, errors


def apply_decision(
    stem: str,
    solution: str,
    reasons: list[str],
    decision: dict[str, Any] | None,
    *,
    check: bool = True,
) -> tuple[str, str, list[str], dict[str, Any] | None]:
    """
    (stem_md, solution_md, review_reasons, evidence) after a decision. Without one nothing changes (evidence is None).
    Approve clears the reasons, but only when both texts are present; hold keeps them and adds the reviewer's reason.
    """
    if not decision:
        return stem, solution, reasons, None
    problems: list[str] = []
    for field in ("stem_md", "explanation_md"):
        text = decision.get(field)
        if text is None:
            continue
        cleaned, errors = _checked(text, check=check)
        if errors:
            problems.append(f"reviewed {field} rejected, kept the previous text: {errors[0]}")
        elif field == "stem_md":
            stem = cleaned
        else:
            solution = cleaned
    verdict = decision.get("verdict")
    evidence = {
        "verdict": verdict,
        "reason": decision.get("reason", ""),
        "fixes": decision.get("fixes", []),
        "printed_issues": decision.get("printed_issues", []),
        "by": REVIEWER,
    }
    if verdict == "approve" and stem.strip() and solution.strip() and not problems:
        return stem, solution, [], evidence
    out = list(reasons) + problems
    if verdict == "hold":
        out.append(f"review hold: {decision.get('reason', '')}")
    elif verdict == "approve":
        out.append("review approved the item but its corrected text failed a gate or is empty")
    return stem, solution, out, evidence


def numeric_key_from(decision: dict[str, Any]) -> dict[str, Any] | None:
    """The key a decision settles on, in the seed's shape; None means the item is not numeric."""
    key = decision.get("numeric_key")
    if not key:
        return None
    try:
        value = Decimal(str(key["numeric_value"]).replace(",", ""))
    except (InvalidOperation, KeyError):
        return None
    return {
        "numeric_value": str(value),
        "tolerance_rel": str(key.get("tolerance_rel") or "0.01"),
        "unit": str(key.get("unit") or ""),
        "key_note": str(key.get("key_note") or "Confirmed against the printed answer in review."),
    }
