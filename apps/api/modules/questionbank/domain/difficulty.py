"""
A first-pass difficulty (1 to 5) for a question that arrives without one (institute PDFs, imports).

It is a transparent heuristic, not a model: the score starts at 2 and moves on what makes a CMA question harder to answer,
longer stems, calculations, statement or negation traps, long-form marks. An editor can always overwrite the result.
Pure and deterministic, so it is safe to run in migrations and repair commands.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from decimal import Decimal

LABELS = {1: "Very easy", 2: "Easy", 3: "Moderate", 4: "Hard", 5: "Very hard"}

_CALC = re.compile(
    r"\b(calculate|compute|determine|ascertain|find the|prepare|net profit|ratio|variance|per unit)\b", re.I
)
_MONEY = re.compile(r"(₹|\brs\.?\s?\d|\brupees\b|\b\d{1,3}(,\d{2,3})+\b|\b\d+(\.\d+)?\s?%)", re.I)
_STATEMENTS = re.compile(
    r"\b(statement\s+(i|1|a)\b|assertion|consider the following|which of the following (is|are) (not|incorrect))", re.I
)
_TRAPS = re.compile(r"\b(both|all of the above|none of the above|only|except|not)\b", re.I)
_SECTION = re.compile(r"\bsection\s+\d+", re.I)


def _words(text: str) -> int:
    return len(re.findall(r"\w+", text or ""))


def estimate_difficulty(
    *,
    kind: str,
    stem: str,
    options: Iterable[str] = (),
    marks: Decimal | float | int = 1,
) -> int:
    """Return 1 (very easy) to 5 (very hard)."""
    option_list = [o for o in options if o]
    score = 2.0

    words = _words(stem)
    if words > 120:
        score += 1.0
    elif words > 60:
        score += 0.5

    text = f"{stem} {' '.join(option_list)}"
    if _CALC.search(stem):
        score += 0.5
    if len(_MONEY.findall(text)) >= 2:
        score += 0.7
    if _STATEMENTS.search(stem):
        score += 0.7
    if any(_TRAPS.search(o) for o in option_list) or re.search(r"\b(not|except)\b", stem, re.I):
        score += 0.4
    if _SECTION.search(text):
        score += 0.2
    if option_list and max(_words(o) for o in option_list) > 25:
        score += 0.3

    if kind in {"long_form", "case_study", "subjective"}:
        m = float(marks)
        score += 1.0 if m >= 10 else 0.5 if m >= 5 else 0.0

    return max(1, min(5, round(score)))
