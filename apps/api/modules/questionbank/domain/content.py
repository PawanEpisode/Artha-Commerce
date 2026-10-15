"""
Question bank rich content linting, text extraction, and hashing.
Builds on `core.richtext` profile 'question' (F-06 PRD 8.2, ERD 2.1, 2.2).
"""

from __future__ import annotations

import hashlib
import json
from decimal import Decimal
from typing import Any

from core.richtext import QUESTION, plain_text, sanitise
from core.richtext import lint as rt_lint


class ContentValidationError(Exception):
    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        super().__init__("; ".join(errors))


def lint_stem(stem_md: str) -> list[str]:
    """Validate question stem against rich text limits."""
    errors: list[str] = []
    if not stem_md or not stem_md.strip():
        errors.append("Question stem cannot be empty.")
        return errors

    if len(stem_md) > QUESTION.max_chars:
        errors.append(f"Question stem exceeds maximum length of {QUESTION.max_chars} characters.")

    issues = rt_lint(stem_md, QUESTION)
    for issue in issues:
        if issue.severity == "error":
            errors.append(f"Stem markdown error at line {issue.line}: {issue.message}")

    return errors


def lint_explanation(explanation_md: str, kind: str, *, is_public: bool = False) -> list[str]:
    """Validate solution / explanation."""
    errors: list[str] = []
    cleaned = (explanation_md or "").strip()

    # Long-form questions always require an explanation
    if kind in ("long_form", "practical") and not cleaned:
        errors.append(f"Explanation/solution is required for {kind} questions.")

    # Public MCQ questions require explanation with 60+ chars (ERD 2.2)
    if is_public and kind in ("mcq_single", "mcq_multi", "true_false"):
        if len(cleaned) < 60:
            errors.append("Public MCQ questions must have an explanation of at least 60 characters.")

    if len(explanation_md or "") > 30_000:
        errors.append("Explanation exceeds maximum length of 30,000 characters.")

    if cleaned:
        issues = rt_lint(explanation_md, QUESTION)
        for issue in issues:
            if issue.severity == "error":
                errors.append(f"Explanation markdown error at line {issue.line}: {issue.message}")

    return errors


def lint_option(body_md: str, position: int) -> list[str]:
    """Validate a single choice option."""
    errors: list[str] = []
    if not body_md or not body_md.strip():
        errors.append(f"Option at position {position} cannot be empty.")
        return errors

    if len(body_md) > 2_000:
        errors.append(f"Option at position {position} exceeds maximum length of 2,000 characters.")

    issues = rt_lint(body_md, QUESTION)
    for issue in issues:
        if issue.severity == "error":
            errors.append(f"Option {position} markdown error: {issue.message}")

    return errors


def extract_search_text(
    stem_md: str,
    option_bodies: list[str] | None = None,
    explanation_md: str = "",
) -> tuple[str, str]:
    """
    Extracts plain text representations:
    1. stem_head: First 300 characters of plain text stem.
    2. search_text: Stem, options, and explanation flattened to plain text, truncated at 10,000 chars.
    """
    clean_stem = plain_text(sanitise(stem_md or "")).strip()
    stem_head = clean_stem[:300]

    parts = [clean_stem]
    if option_bodies:
        for opt in option_bodies:
            parts.append(plain_text(sanitise(opt or "")).strip())

    if explanation_md:
        parts.append(plain_text(sanitise(explanation_md)).strip())

    combined = " \n ".join(p for p in parts if p)
    search_text = combined[:10_000]

    return stem_head, search_text


def compute_content_hash(
    stem_md: str,
    options: list[dict[str, Any]] | None = None,
    numeric_key: dict[str, Any] | None = None,
    rubric: dict[str, Any] | None = None,
    marks: Decimal | float | int = 1,
) -> str:
    """
    Computes canonical SHA-256 hash of question version content:
    stem, options in order, numeric key, rubric, and marks (ERD 2.2).
    """
    canonical_data = {
        "stem": sanitise(stem_md or "").strip(),
        "options": [
            {
                "position": opt.get("position", i),
                "body": sanitise(opt.get("body_md", "")).strip(),
                "is_correct": bool(opt.get("is_correct", False)),
                "pinned": bool(opt.get("pinned", False)),
            }
            for i, opt in enumerate(options or [])
        ],
        "numeric_key": (
            {
                "value": str(numeric_key.get("numeric_value")),
                "tol_abs": str(numeric_key.get("tolerance_abs", 0)),
                "tol_rel": str(numeric_key.get("tolerance_rel", 0)),
            }
            if numeric_key
            else None
        ),
        "rubric": (
            {
                "solution": sanitise(rubric.get("reference_solution_md", "")).strip(),
                "steps": [
                    {
                        "pos": step.get("position", i),
                        "title": step.get("title", ""),
                        "marks": str(step.get("marks", 0)),
                    }
                    for i, step in enumerate(rubric.get("steps", []))
                ],
            }
            if rubric
            else None
        ),
        "marks": str(marks),
    }

    serialized = json.dumps(canonical_data, sort_keys=True, ensure_ascii=True)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()
