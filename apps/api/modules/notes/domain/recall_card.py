"""
What a recall card made from a mark looks like (slice 19), pure. The kind comes from the colour's meaning in the student's
own legend (they may rename "Formula" to anything), so the name is tried first and the colour's default meaning second.
"""

from __future__ import annotations

from collections.abc import Mapping

from core.recall_port import CARD_KINDS

# meaning (casefolded, the default legend names) -> card kind
_BY_MEANING = {
    "formula": "formula",
    "section or rule": "rule",
    "doubt": "doubt",
    "example": "example",
    "important": "fact",
}
# the colour keys' default meaning, for a legend the student renamed away from the defaults
_BY_COLOR = {"y": "fact", "g": "formula", "b": "rule", "p": "doubt", "o": "example"}

_PROMPTS = {
    "formula": "State the formula",
    "rule": "State the rule",
    "definition": "Define it",
    "example": "Recall the example",
    "doubt": "Clear this doubt",
    "fact": "Recall this point",
}


def card_kind_for_color(color: str | None, legend: Mapping[str, str] | None) -> str:
    """Formula -> formula, Section or rule -> rule, Doubt -> doubt, Example -> example, Important -> fact; default `fact`."""
    meaning = " ".join(((legend or {}).get(color or "") or "").split()).casefold()
    return _BY_MEANING.get(meaning) or _BY_COLOR.get(color or "", "fact")


def valid_kind(kind: str | None) -> bool:
    return kind in CARD_KINDS


def front_prompt(kind: str, *, chapter_name: str | None, page: int) -> str:
    """The question side: what to recall, where from. Never the mark's own text (that is the answer)."""
    where = chapter_name or "your PDF"
    return f"{_PROMPTS.get(kind, _PROMPTS['fact'])} from {where} (page {page})."


def back_text(quote: str | None, comment: str | None) -> str:
    """The answer side: the quoted text, then the student's comment when there is one. Empty when the mark has neither."""
    quote, comment = (quote or "").strip(), (comment or "").strip()
    return "\n\n".join(part for part in (quote, comment) if part)
