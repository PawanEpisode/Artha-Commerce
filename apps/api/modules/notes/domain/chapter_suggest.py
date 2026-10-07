"""
One-tap chapter suggestions for unfiled notes (FR-F03-39): a pure text match against chapter and subject names, no AI.

Each chapter name is scored by how much of its (weighted) vocabulary appears in the note text. A word that occurs in few
chapter names is worth more than one that occurs in many ("credit" in a dozen chapters says little, "apportionment" says a
lot). A whole-name hit and a subject-name hit add a little. Only a clear match is returned, at most `LIMIT` of them.
"""

from __future__ import annotations

import math
import re
from collections.abc import Sequence
from dataclasses import dataclass

LIMIT = 3
THRESHOLD = 0.34
_STOP = frozenset(
    "the and for with that this from are was were has have not but under over into about when what which also can any all "
    "its their your our out use used using per than then them they you act law rule rules chapter paper section sections".split()
)
_WORD = re.compile(r"[^\W_]+", re.UNICODE)


@dataclass(frozen=True)
class Candidate:
    chapter_id: object
    chapter_key: str
    chapter_name: str
    subject_id: object
    subject_key: str
    subject_name: str


@dataclass(frozen=True)
class Suggestion:
    candidate: Candidate
    score: float


def _stem(word: str) -> str:
    if len(word) > 4 and word.endswith("ies"):
        return word[:-3] + "y"
    if len(word) > 3 and word.endswith("s") and not word.endswith("ss"):
        return word[:-1]
    return word


def tokens(text: str) -> list[str]:
    """Lower-case stems of the meaningful words (3+ letters or any number, no stop words), in order."""
    out = []
    for raw in _WORD.findall(text.casefold()):
        if raw in _STOP or (len(raw) < 3 and not raw.isdigit()):
            continue
        out.append(_stem(raw))
    return out


def suggest(text: str, candidates: Sequence[Candidate], *, limit: int = LIMIT) -> list[Suggestion]:
    words = set(tokens(text))
    if not words or not candidates:
        return []
    chapter_tokens = [set(tokens(c.chapter_name)) for c in candidates]
    document_frequency: dict[str, int] = {}
    for toks in chapter_tokens:
        for t in toks:
            document_frequency[t] = document_frequency.get(t, 0) + 1
    n = len(candidates)

    def weight(token: str) -> float:
        return math.log(1 + n / document_frequency.get(token, 1))

    flat = " ".join(tokens(text))
    scored = []
    for candidate, toks in zip(candidates, chapter_tokens, strict=True):
        if not toks:
            continue
        total = sum(weight(t) for t in toks)
        hit = sum(weight(t) for t in toks if t in words)
        score = hit / total if total else 0.0
        if score > 0 and " ".join(tokens(candidate.chapter_name)) in flat:
            score += 0.25  # the whole name appears in order
        subject_words = set(tokens(candidate.subject_name))
        if score > 0 and subject_words and subject_words & words:
            score += 0.1
        if score >= THRESHOLD:
            scored.append(Suggestion(candidate, round(score, 3)))
    scored.sort(key=lambda s: (-s.score, s.candidate.chapter_name))
    return scored[:limit]
