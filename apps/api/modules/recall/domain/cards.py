"""
Card kinds (PRD 4.4, ERD 3.6): typed fields, structural validation, a pure `render` to front and back Markdown, the cloze
parser, the rule-based kind suggestion for a selection, and the duplicate fingerprint. Markdown safety (KaTeX rules, no raw
HTML) is the `card` profile of `core.richtext`, applied by the services; this module only checks structure.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping
from dataclasses import dataclass

from .limits import FIELD_MAX_CHARS, MAX_CLOZES, SHORT_FIELD_MAX_CHARS

KINDS = ("pointer", "formula", "section", "definition", "mnemonic", "case_law", "cloze")
FIELDS_VERSION = 1


@dataclass(frozen=True)
class FieldSpec:
    name: str
    required: bool = True
    short: bool = False  # plain one-line field, at most 200 characters; others are Markdown up to 4,000


@dataclass(frozen=True)
class Issue:
    field: str
    code: str
    message: str


SPECS: dict[str, tuple[FieldSpec, ...]] = {
    "pointer": (FieldSpec("prompt_md"), FieldSpec("answer_md")),
    "formula": (
        FieldSpec("name", short=True),
        FieldSpec("expression_md"),
        FieldSpec("variables_md", required=False),
        FieldSpec("when_md", required=False),
    ),
    "section": (
        FieldSpec("act", required=False, short=True),
        FieldSpec("reference", short=True),
        FieldSpec("prompt_md"),
        FieldSpec("gist_md"),
        FieldSpec("exceptions_md", required=False),
    ),
    "definition": (
        FieldSpec("term", short=True),
        FieldSpec("definition_md"),
        FieldSpec("source_ref", required=False, short=True),
    ),
    "mnemonic": (
        FieldSpec("mnemonic", short=True),
        FieldSpec("expands_md"),
        FieldSpec("topic", required=False, short=True),
    ),
    "case_law": (
        FieldSpec("case_name", short=True),
        FieldSpec("citation", required=False, short=True),
        FieldSpec("court", required=False, short=True),
        FieldSpec("year", required=False, short=True),
        FieldSpec("facts_md", required=False),
        FieldSpec("held_md"),
    ),
    "cloze": (FieldSpec("text_md"),),
}

# {{c1::answer}} or {{c1::answer::hint}}; answers may not contain "}}"; non-greedy so two clozes on a line stay separate
CLOZE = re.compile(r"\{\{c(\d+)::(.*?)(?:::(.*?))?\}\}", re.DOTALL)


def cloze_numbers(text: str) -> list[int]:
    return [int(m.group(1)) for m in CLOZE.finditer(text)]


def validate(kind: str, fields: Mapping[str, object]) -> list[Issue]:
    """Structural problems of a card's fields; an empty list means it can be saved (after the Markdown lint)."""
    if kind not in SPECS:
        return [Issue("kind", "unknown_kind", f"Unknown card kind {kind!r}.")]
    issues: list[Issue] = []
    spec_names = {f.name for f in SPECS[kind]}
    for name in fields:
        if name not in spec_names and name != "v":
            issues.append(Issue(str(name), "unknown_field", f"{name} is not a field of a {kind} card."))
    for spec in SPECS[kind]:
        raw = fields.get(spec.name, "")
        if raw is None:
            raw = ""
        if not isinstance(raw, str):
            issues.append(Issue(spec.name, "not_text", f"{spec.name} must be text."))
            continue
        value = raw.strip()
        limit = SHORT_FIELD_MAX_CHARS if spec.short else FIELD_MAX_CHARS
        if spec.required and not value:
            issues.append(Issue(spec.name, "required", f"{spec.name} is required."))
        elif len(value) > limit:
            issues.append(Issue(spec.name, "too_long", f"{spec.name} is longer than {limit} characters."))
        elif spec.short and "\n" in value:
            issues.append(Issue(spec.name, "single_line", f"{spec.name} must be one line."))
    if kind == "cloze" and isinstance(fields.get("text_md"), str):
        issues.extend(_cloze_issues(fields["text_md"]))  # type: ignore[arg-type]
    return issues


def _cloze_issues(text: str) -> list[Issue]:
    numbers = cloze_numbers(text)
    if not numbers:
        return [Issue("text_md", "cloze_none", "Add at least one {{c1::...}} deletion.")]
    if len(numbers) > MAX_CLOZES:
        return [Issue("text_md", "cloze_too_many", f"At most {MAX_CLOZES} deletions are allowed.")]
    if len(set(numbers)) != len(numbers):
        return [Issue("text_md", "cloze_duplicate", "Each deletion needs its own number: c1, c2, c3 ...")]
    if sorted(numbers) != list(range(1, len(numbers) + 1)):
        return [Issue("text_md", "cloze_gap", "Deletion numbers must run 1, 2, 3 ... without gaps.")]
    return []


def ordinals(kind: str, fields: Mapping[str, object]) -> list[int]:
    """The card faces of an item: one per cloze number, else the single default face 0."""
    if kind == "cloze":
        return sorted(cloze_numbers(str(fields.get("text_md", ""))))
    return [0]


def _s(fields: Mapping[str, object], name: str) -> str:
    value = fields.get(name)
    return value.strip() if isinstance(value, str) else ""


def _join(*parts: str) -> str:
    return "\n\n".join(p for p in parts if p)


def render(kind: str, fields: Mapping[str, object], ordinal: int = 0) -> tuple[str, str]:
    """Front and back Markdown of one card face. Pure: the same fields render the same on the server and in the offline pack."""
    if kind == "pointer":
        return _s(fields, "prompt_md"), _s(fields, "answer_md")
    if kind == "formula":
        hint = _s(fields, "when_md")
        return (
            _join(f"**{_s(fields, 'name')}**", f"When to use: {hint}" if hint else ""),
            _join(_s(fields, "expression_md"), _s(fields, "variables_md")),
        )
    if kind == "section":
        head = " ".join(p for p in (_s(fields, "act"), _s(fields, "reference")) if p)
        exceptions = _s(fields, "exceptions_md")
        return (
            _join(f"**{head}**", _s(fields, "prompt_md")),
            _join(_s(fields, "gist_md"), f"**Exceptions**\n\n{exceptions}" if exceptions else ""),
        )
    if kind == "definition":
        source = _s(fields, "source_ref")
        return f"**{_s(fields, 'term')}**", _join(_s(fields, "definition_md"), f"Source: {source}" if source else "")
    if kind == "mnemonic":
        return (
            _join(_s(fields, "topic"), f"**{_s(fields, 'mnemonic')}**", "What does it stand for?"),
            _s(fields, "expands_md"),
        )
    if kind == "case_law":
        cite = ", ".join(p for p in (_s(fields, "citation"), _s(fields, "court"), _s(fields, "year")) if p)
        return (
            _join(f"**{_s(fields, 'case_name')}**", _s(fields, "facts_md")),
            _join(_s(fields, "held_md"), cite),
        )
    if kind == "cloze":
        text = _s(fields, "text_md")

        def front(m: re.Match[str]) -> str:
            if int(m.group(1)) == ordinal:
                return f"[{m.group(3)}]" if m.group(3) else "[...]"
            return m.group(2)

        def back(m: re.Match[str]) -> str:
            return f"**{m.group(2)}**" if int(m.group(1)) == ordinal else m.group(2)

        return CLOZE.sub(front, text), CLOZE.sub(back, text)
    raise ValueError(f"Unknown card kind {kind!r}")


_SECTION = re.compile(r"\b(?:section|sec\.?|rule|article|regulation)\s+\d+", re.IGNORECASE)
_DEFINITION = re.compile(r"\b(?:means|is defined as|are defined as|shall mean|refers to)\b", re.IGNORECASE)
_CASE = re.compile(r"\b[A-Z][\w.&'-]*(?:\s+[A-Z][\w.&'-]*)*\s+(?:v\.?|vs\.?)\s+[A-Z]", re.UNICODE)
_COURT = re.compile(r"\b(?:supreme court|high court|tribunal|itat|nclt|nclat|sc|hc)\b", re.IGNORECASE)


def suggest_kind(selection_text: str) -> tuple[str, float]:
    """Best kind for a selected passage, by pure rules (FR-F15-15), with a 0 to 1 score. The student can always change it."""
    text = selection_text.strip()
    scores = {
        "case_law": 0.9 if _CASE.search(text) and _COURT.search(text) else (0.6 if _CASE.search(text) else 0.0),
        "section": 0.85 if _SECTION.search(text) else 0.0,
        "formula": 0.8 if ("=" in text or "\\frac" in text or "$" in text) else 0.0,
        "definition": 0.7 if _DEFINITION.search(text) else 0.0,
    }
    kind, score = max(scores.items(), key=lambda kv: kv[1])
    return (kind, score) if score > 0 else ("pointer", 0.3)


_SPACE = re.compile(r"\s+")


def fingerprint(kind: str, fields: Mapping[str, object]) -> str:
    """SHA-256 of the normalised text of the face fields (lower case, collapsed whitespace, no `$`, no LaTeX spacing)."""
    front, back = render(kind, fields, 1 if kind == "cloze" else 0) if kind != "cloze" else (_s(fields, "text_md"), "")
    text = f"{front}\n{back}".lower().replace("$", "").replace("\\,", "").replace("\\;", "").replace("\\!", "")
    return hashlib.sha256(_SPACE.sub(" ", text).strip().encode()).hexdigest()
