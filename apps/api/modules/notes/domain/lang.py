"""
Language detection for search (ERD 2.3), pure. One place for the rule so notes, marks and the PDF page worker agree.

Postgres needs one text search configuration per stored vector: `english` stems Latin text ("credits" matches "credit"),
which would mangle Hindi, so Hindi and mixed text use `simple` (no stemming, no stop words). The rule: Devanagari letters
above 30% of all letters means `simple`. `detect_lang` gives the finer label stored in `lang` (`en`, `hi`, `mixed`).

Import `detect_lang`, `detect_search_config` (alias `config_for_text`) and `config_for` from here (`search_query` re-exports them).
"""

from __future__ import annotations

import unicodedata

DEVANAGARI_MIXED_ABOVE = 0.3  # more Devanagari than this share of letters: stop stemming
DEVANAGARI_HINDI_ABOVE = 0.7  # more than this: the text is Hindi, not mixed


def _is_letter(ch: str) -> bool:
    """A letter or a combining mark (Devanagari vowel signs are marks, and belong to the word they are in)."""
    return unicodedata.category(ch)[0] in "LM"


def devanagari_share(text: str) -> float:
    """Devanagari letters and vowel signs as a share of all letters and vowel signs (0 to 1); 0 for text without letters.
    Digits, spaces, punctuation and the danda are not counted on either side."""
    letters = [ch for ch in text if _is_letter(ch)]
    return sum(1 for ch in letters if "\u0900" <= ch <= "\u097f") / len(letters) if letters else 0.0


def detect_lang(text: str) -> str:
    """`en` (Latin script), `hi` (mostly Devanagari) or `mixed`."""
    share = devanagari_share(text)
    if share > DEVANAGARI_HINDI_ABOVE:
        return "hi"
    return "mixed" if share > DEVANAGARI_MIXED_ABOVE else "en"


def config_for(lang: str) -> str:
    """The Postgres text search configuration for a stored `lang`."""
    return "english" if lang == "en" else "simple"


def detect_search_config(text: str) -> str:
    """`simple` when Devanagari exceeds 30% of the letters, else `english`: what to build the `tsvector` with."""
    return config_for(detect_lang(text))


config_for_text = detect_search_config  # the name the search index service uses; same function
