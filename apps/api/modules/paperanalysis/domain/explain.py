"""
Reason sentence templates, caveats, and copy linting for F-11.
Reference: PRD 7.5 and ERD 3.5.
"""

from __future__ import annotations

import re
from typing import Any

TEMPLATE_VERSION = 1
DISCLAIMER_KEY = "history_not_guarantee_v1"
DISCLAIMER_TEXT = (
    "Based on past papers. History is not a guarantee. The Institute can ask from any chapter, "
    "so keep covering the whole syllabus."
)

FORBIDDEN_PHRASES = [
    "guaranteed",
    "sure shot",
    "will come",
    "predicted",
    "skip",
    "important for sure",
]

TEMPLATES: dict[str, str] = {
    "asked_in_window": "Carried up to {max} marks and appeared in {asked_n} of the last {window_n} sittings",
    "avg_when_asked": "Carried {avg} marks on average in the {asked_n} of the last {window_n} sittings where it appeared",
    "high_expected_marks": "Among the heaviest in this paper in past sittings: about {share_pct}% of the marks (an estimate from history)",
    "rising_trend": "Marks have been rising: {recent} on average in the last 3 sittings against {earlier} before",
    "falling_trend": "Marks have been lower: {recent} on average in the last 3 sittings against {earlier} before",
    "weak_practice": "You answered {correct} of {answered} practice questions correctly here",
    "not_enough_practice": "Not enough practice yet to judge your strength here ({answered} answers)",
    "low_coverage": "You have covered {cov_pct}% of this chapter",
    "high_coverage": "You have covered {cov_pct}% of this chapter, so revising is a lower priority",
    "urgency_shift": "With {days_left} days left, expected marks count more than weak spots",
    "official_weight": "The Institute's published weight for this section is {lo} to {hi} marks",
    "effort_estimate": "About {hours} hours {basis}; roughly {mph} expected marks per hour",
    # Caveats
    "limited_history": "Only {papers_n} sittings of history, so treat this as a rough guide",
    "carried_history": "Includes {carried_n} papers from earlier scheme",
    "restructured": "This chapter was restructured, so earlier papers are not counted",
    "new_chapter": "New chapter with no paper history; the subject average is used",
    "practice_papers_only": "Based on practice papers only",
}


def render_reason(code: str, params: dict[str, Any]) -> str:
    """Renders a structured reason code and params into a validated sentence."""
    template = TEMPLATES.get(code)
    if not template:
        return f"Reason: {code}"
    try:
        sentence = template.format(**params)
        lint_copy(sentence)
        return sentence
    except KeyError:
        return f"Reason: {code}"


def lint_copy(text: str) -> None:
    """
    Enforces FR-F11-41: forbidden phrases fail copy linting.
    """
    lower = text.lower()
    for phrase in FORBIDDEN_PHRASES:
        pattern = r"\b" + re.escape(phrase) + r"\b"
        if re.search(pattern, lower):
            raise ValueError(f"Forbidden phrase '{phrase}' found in copy: '{text}'")


def explain_reasons(
    components: dict[str, float],
    asked_n: int,
    window_n: int,
    max_marks: float,
    trend_direction: str,
    coverage: float,
    accuracy: float,
    attempts_count: int,
    days_left: int,
) -> list[dict[str, Any]]:
    """
    Produces list of structured reasons with code, params, and validated sentence.
    """
    reasons = []
    if asked_n > 0 and window_n > 0:
        params = {"max": max_marks, "asked_n": asked_n, "window_n": window_n}
        reasons.append({
            "code": "asked_in_window",
            "params": params,
            "sentence": render_reason("asked_in_window", params),
        })

    if days_left <= 30:
        params = {"days_left": days_left}
        reasons.append({
            "code": "urgency_shift",
            "params": params,
            "sentence": render_reason("urgency_shift", params),
        })

    if attempts_count >= 5:
        correct = int(round(accuracy * attempts_count))
        params = {"correct": correct, "answered": attempts_count}
        reasons.append({
            "code": "weak_practice",
            "params": params,
            "sentence": render_reason("weak_practice", params),
        })

    return reasons


def chapter_caveats(
    comparability: str,
    is_limited: bool = False,
    papers_n: int = 6,
) -> list[dict[str, Any]]:
    """
    Produces structured caveats for a chapter based on comparability and data status.
    """
    caveats = []
    if is_limited:
        params = {"papers_n": papers_n}
        caveats.append({
            "code": "limited_history",
            "params": params,
            "sentence": render_reason("limited_history", params),
        })

    if comparability == "carried":
        params = {"carried_n": 4}
        caveats.append({
            "code": "carried_history",
            "params": params,
            "sentence": render_reason("carried_history", params),
        })
    elif comparability == "restructured":
        params = {}
        caveats.append({
            "code": "restructured",
            "params": params,
            "sentence": render_reason("restructured", params),
        })
    elif comparability == "new":
        params = {}
        caveats.append({
            "code": "new_chapter",
            "params": params,
            "sentence": render_reason("new_chapter", params),
        })

    return caveats
