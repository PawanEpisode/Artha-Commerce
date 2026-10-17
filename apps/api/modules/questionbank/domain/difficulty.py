"""
A first-pass difficulty (1 to 5) for a question that arrives without one (institute PDFs, imports).

It is a transparent heuristic, not a model: the score starts near 2 and moves on what makes a CMA question harder to
answer. An editor can always overwrite the result. Pure and deterministic, so it is safe to run in migrations and repair
commands.

Version 2 (written against the real CMA Final data): the first version gave every long-form question of 7 marks or more a
5, so the column carried no information. Long-form questions are now scored on the work they ask for: how many parts,
how many figures and tables, how long the worked solution is, whether the topic is an advanced one, and only then marks.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from decimal import Decimal

LABELS = {1: "Very easy", 2: "Easy", 3: "Moderate", 4: "Hard", 5: "Very hard"}

LONG_KINDS = {"long_form", "case_study", "subjective", "practical"}

_CALC = re.compile(
    r"\b(calculate|compute|determine|ascertain|find the|prepare|net profit|ratio|variance|per unit|what (will|would) be|how much)\b",
    re.I,
)
_MONEY = re.compile(r"(₹|\brs\.?\s?\d|\brupees\b|\b\d{1,3}(,\d{2,3})+\b|\b\d+(\.\d+)?\s?%)", re.I)
_NUMBER = re.compile(r"(?<![A-Za-z])\d[\d,]*(?:\.\d+)?")
_STATEMENTS = re.compile(
    r"\b(statement\s+(i|1|a)\b|assertion|consider the following|which of the following (is|are) (not|incorrect))", re.I
)
_TRAPS = re.compile(r"\b(both|all of the above|none of the above|only|except|not)\b", re.I)
_SECTION = re.compile(r"\bsection\s+\d+", re.I)
_PART = re.compile(r"(?m)^\s*(?:\(?[a-h]\)|\(?(?:i{1,3}|iv|v|vi{0,3}|ix|x)\)|\(?[1-9]\)|[a-h]\.)\s+\S")
_ADVANCED = re.compile(
    r"\b(irr|npv|wacc|hedg\w+|swap|option|futures?|arbitrage|duration|beta|capm|merger|amalgamation|consolidat\w+|"
    r"transfer pricing|input tax credit|itc|place of supply|valuation|goodwill|linear programming|simplex|"
    r"transportation|assignment problem|sensitivity|simulation|regression|abc costing|target costing|"
    r"residual income|balanced scorecard|dcf|free cash flow|eva|forex|forward contract|derivative)\b",
    re.I,
)
_THEORY = re.compile(
    r"\b(explain|discuss|describe|state|write (short )?notes?|define|distinguish|list|enumerate|comment)\b", re.I
)
_TABLE = re.compile(r"(?m)^\s*\|.*\|\s*$|^```")


def _words(text: str) -> int:
    return len(re.findall(r"\w+", text or ""))


def _objective_score(stem: str, option_list: list[str]) -> float:
    score = 2.0
    words = _words(stem)
    if words > 120:
        score += 1.0
    elif words > 60:
        score += 0.5
    elif words <= 12 and not _CALC.search(stem):
        score -= 0.6  # a one-line recall question ("Who issues the certificate of incorporation?")

    text = f"{stem} {' '.join(option_list)}"
    numbers = len(_NUMBER.findall(stem))
    if _CALC.search(stem) and numbers >= 3:
        score += 1.0  # a worked calculation inside a multiple choice question
    elif _CALC.search(stem):
        score += 0.4
    if len(_MONEY.findall(text)) >= 2:
        score += 0.5
    if _STATEMENTS.search(stem):
        score += 0.7
    if any(_TRAPS.search(o) for o in option_list) or re.search(r"\b(not|except)\b", stem, re.I):
        score += 0.4
    if _SECTION.search(text):
        score += 0.2
    if _ADVANCED.search(stem):
        score += 0.3
    if option_list and max(_words(o) for o in option_list) > 25:
        score += 0.3
    return score


def _long_form_score(stem: str, solution: str, marks: float) -> float:
    score = 1.3
    numbers = len(_NUMBER.findall(stem))
    calculation = bool(_CALC.search(stem)) or numbers >= 6

    if calculation:
        score += 0.4
        if numbers >= 40:
            score += 1.0
        elif numbers >= 18:
            score += 0.7
        elif numbers >= 8:
            score += 0.4
    elif _THEORY.search(stem):
        score -= 0.4  # theory answers are long but not hard in the way a computation is

    parts = len(_PART.findall(stem))
    score += min(1.0, 0.25 * max(0, parts - 1))

    if _TABLE.search(stem):
        score += 0.4
    words = _words(stem)
    if words > 250:
        score += 0.5
    elif words > 150:
        score += 0.3
    if _ADVANCED.search(stem):
        score += 0.4

    if solution:
        size = len(solution)
        steps = solution.count("=")
        if size > 6000 or steps > 40:
            score += 0.9
        elif size > 3000 or steps > 20:
            score += 0.6
        elif size > 1200 or steps > 8:
            score += 0.3
        if len(_TABLE.findall(solution)) >= 4:
            score += 0.3

    if marks >= 10:
        score += 0.9
    elif marks >= 7:
        score += 0.5
    elif marks >= 4:
        score += 0.2
    return score


def estimate_difficulty(
    *,
    kind: str,
    stem: str,
    options: Iterable[str] = (),
    marks: Decimal | float | int = 1,
    solution: str = "",
) -> int:
    """Return 1 (very easy) to 5 (very hard). `solution` is optional and, when given, sharpens long-form scores."""
    stem = stem or ""
    if kind in LONG_KINDS:
        score = _long_form_score(stem, solution or "", float(marks or 0))
    else:
        score = _objective_score(stem, [o for o in options if o])
    return max(1, min(5, round(score)))
