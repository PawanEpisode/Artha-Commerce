"""
Search text helpers (ERD 6.3), all pure: a reference-aware query preprocessor, language detection that picks the stored
vector's configuration, query terms for the SQLite fallback and snippets around a match.

The English parser splits "17(5)" and "Ind AS 115" into pieces that match far too much. `prepare_query` quotes tokens that
contain digits and brackets so `websearch_to_tsquery` treats them as phrases.
"""

from __future__ import annotations

import re
import unicodedata

MAX_QUERY = 200
_WORD = re.compile(r"\w+", re.UNICODE)
_DEVANAGARI = re.compile("[ऀ-ॿ]")
_LETTER = re.compile(r"[^\W\d_]", re.UNICODE)


def _is_reference(token: str) -> bool:
    return not token.startswith('"') and any(c.isdigit() for c in token) and "(" in token and ")" in token


def clean_query(q: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", q).split())[:MAX_QUERY]


def prepare_query(q: str) -> str:
    """The query as `websearch_to_tsquery` should read it: reference-like tokens (digits with brackets) become phrases."""
    tokens = clean_query(q).split()
    return " ".join(f'"{t}"' if _is_reference(t) else t for t in tokens)


def terms(q: str) -> list[str]:
    """Lower-case words of a query for substring matching and snippets; digits and brackets stay together as a reference."""
    cleaned = clean_query(q).replace('"', " ")
    out = []
    for token in cleaned.split():
        folded = token.casefold().strip(".,;:!?")
        if folded and folded not in out and folded not in {"or", "and", "-"} and not folded.startswith("-"):
            out.append(folded)
    return out


def detect_lang(text: str) -> str:
    """`en` (Latin script), `hi` (mostly Devanagari) or `mixed`. Decides between the `english` and `simple` configurations."""
    letters = len(_LETTER.findall(text)) or 1
    share = len(_DEVANAGARI.findall(text)) / letters
    if share > 0.7:
        return "hi"
    return "mixed" if share > 0.3 else "en"


def config_for(lang: str) -> str:
    return "english" if lang == "en" else "simple"


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
