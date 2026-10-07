"""
Search text helpers (ERD 6.3), all pure: a reference-aware query preprocessor, query terms for the SQLite fallback and
snippets around a match. Language detection lives in `lang.py` (re-exported here for existing imports).

The English parser splits "17(5)" and "Ind AS 115" into pieces that match far too much. `prepare_query` turns references
into phrases for `websearch_to_tsquery`: a token with digits and brackets ("17(5)") and a citation prefix followed by a number
("Section 149", "Ind AS 115", "SA 200", "AS 2"). The TypeScript twin is `web/.../lib/search-query.ts` (`prepareQuery`), both
read `tests/fixtures/search_query_cases.json`.
"""

from __future__ import annotations

import re
import unicodedata

from .lang import (  # noqa: F401 - re-exported: callers import them from here
    config_for,
    config_for_text,
    detect_lang,
    detect_search_config,
)

MAX_QUERY = 200
_TOKEN = re.compile(r'"[^"]*"|\S+')  # a quoted phrase stays one token
_NUMBER = re.compile(r"[0-9]+[A-Za-z]{0,3}")  # 149, 80C, 115BAA, 143A
# Words that make the number after them one thing to search for. "ind as" is handled on its own (two words).
_CITATION_PREFIXES = frozenset(
    {
        "section",
        "sec",
        "rule",
        "regulation",
        "reg",
        "clause",
        "article",
        "schedule",
        "para",
        "paragraph",
        "sa",
        "as",
        "ifrs",
        "ias",
    }
)


def _is_reference(token: str) -> bool:
    """Digits with brackets, such as `17(5)` or `16(2)(a)`."""
    return not token.startswith('"') and any(c.isdecimal() for c in token) and "(" in token and ")" in token


def _is_number(token: str) -> bool:
    return not token.startswith('"') and _NUMBER.fullmatch(token.rstrip(".,;:!?")) is not None


def clean_query(q: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", q).split())[:MAX_QUERY]


def prepare_query(q: str) -> str:
    """
    The query as `websearch_to_tsquery` should read it: references become phrases. `17(5)` -> `"17(5)"`, `Section 149` ->
    `"Section 149"`, `Ind AS 115` -> `"Ind AS 115"`. A bracketed reference after a prefix stays separate (`section "16(2)"`),
    already quoted phrases are left alone, and trailing punctuation after a number is dropped from the phrase.
    """
    tokens = _TOKEN.findall(clean_query(q))
    out: list[str] = []
    i = 0
    while i < len(tokens):
        low = tokens[i].casefold()
        if low == "ind" and i + 2 < len(tokens) and tokens[i + 1].casefold() == "as" and _is_number(tokens[i + 2]):
            width = 3
        elif low in _CITATION_PREFIXES and i + 1 < len(tokens) and _is_number(tokens[i + 1]):
            width = 2
        else:
            width = 0
        if width:
            out.append('"' + " ".join([*tokens[i : i + width - 1], tokens[i + width - 1].rstrip(".,;:!?")]) + '"')
            i += width
        else:
            out.append(f'"{tokens[i]}"' if _is_reference(tokens[i]) else tokens[i])
            i += 1
    return " ".join(out)


def terms(q: str) -> list[str]:
    """Lower-case words of a query for substring matching and snippets; digits and brackets stay together as a reference."""
    cleaned = clean_query(q).replace('"', " ")
    out = []
    for token in cleaned.split():
        folded = token.casefold().strip(".,;:!?")
        if folded and folded not in out and folded not in {"or", "and", "-"} and not folded.startswith("-"):
            out.append(folded)
    return out


def make_snippet(text: str, query_terms: list[str], width: int = 160) -> str:
    """About `width` characters around the first matching term (or the start), on word edges, with ellipses when cut."""
    flat = " ".join(text.split())
    if len(flat) <= width:
        return flat
    lowered = flat.casefold()
    hit = min((i for i in (lowered.find(t) for t in query_terms) if i >= 0), default=0)
    start = max(0, hit - width // 4)
    end = min(len(flat), start + width)
    start = max(0, end - width)
    if start > 0:
        start = flat.find(" ", start) + 1 or start
    if end < len(flat):
        end = flat.rfind(" ", start, end) if flat.rfind(" ", start, end) > start else end
    return ("…" if start > 0 else "") + flat[start:end].strip() + ("…" if end < len(flat) else "")
