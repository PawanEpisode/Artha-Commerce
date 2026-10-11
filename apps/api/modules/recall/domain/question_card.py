"""
The card a mistake makes (FR-F15-17), as a pure function of what the question bank supplied. Nothing here reads the database or
calls a model: the front asks for the rule the question cited, the back quotes the bank's own explanation and names its source.
Anything the card profile would refuse (headings, images) is flattened first so a good explanation never fails the save.
"""

from __future__ import annotations

import re

MAX_LABELS = 3
EXPLANATION_MAX = 1500  # characters of the explanation kept on the back; the card field allows 4,000
LABEL_MAX = 120

_HEADING = re.compile(r"^\s{0,3}#{1,6}\s*", re.M)
_IMAGE = re.compile(r"!\[([^\]]*)\]\([^)]*\)")
_BLANKS = re.compile(r"\n{3,}")


def flatten(markdown: str) -> str:
    """The explanation without headings or images (an image keeps its alt text), with at most one blank line in a row."""
    text = _IMAGE.sub(lambda m: m.group(1), markdown.replace("\r\n", "\n").replace("\r", "\n"))
    text = _HEADING.sub("", text)
    return _BLANKS.sub("\n\n", text).strip()


def _clip(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit(None, 1)[0] if " " in text[:limit] else text[:limit]
    return cut.rstrip(" ,;:.") + "…"


def labels_of(labels: tuple[str, ...] | list[str]) -> list[str]:
    """Distinct, non-empty reference labels in the order given, each short, at most `MAX_LABELS`."""
    seen: list[str] = []
    for raw in labels:
        label = _clip(" ".join(str(raw).split()), LABEL_MAX)
        if label and label not in seen:
            seen.append(label)
    return seen[:MAX_LABELS]


def build_fields(
    explanation_md: str, reference_labels: tuple[str, ...] | list[str], source_label: str = ""
) -> dict | None:
    """
    `{prompt_md, answer_md}` of a pointer card, or None when the bank gave neither an explanation nor a reference (there is
    nothing true to put on the back, and a card is never made up).
    """
    explanation = _clip(flatten(explanation_md or ""), EXPLANATION_MAX)
    labels = labels_of(reference_labels)
    if not explanation and not labels:
        return None
    if labels:
        prompt = "What is the rule in " + " and ".join(labels) + "?"
    else:
        prompt = "What rule did this question test?"
    parts = [explanation] if explanation else []
    source = "; ".join(labels)
    if source_label.strip():
        source = (
            f"{source} ({_clip(' '.join(source_label.split()), LABEL_MAX)})"
            if source
            else _clip(" ".join(source_label.split()), LABEL_MAX)
        )
    if source:
        parts.append(f"Source: {source}")
    return {"prompt_md": prompt, "answer_md": "\n\n".join(parts)}
