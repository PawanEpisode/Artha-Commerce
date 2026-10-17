"""
Chapter classifier: which syllabus chapter does a question belong to?

A transparent keyword scorer, not a model. Each chapter is described by its name (heavy weight) and its topic names
(light weight); words that appear in only one chapter of the paper count more (inverse chapter frequency). Question banks
are printed in syllabus order, so `classify_sequence` also uses the neighbours: it picks the best path through the
chapters, charging a small price for moving to a later chapter and a large one for moving back.

Every result carries a confidence. The loader stores low-confidence results as *suggested* mappings so an editor can see
which ones to confirm; nothing here is ever presented as an editor decision.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass

_STOP = frozenset(
    """a an and are as at be by for from has have in is it its of on or that the their this to under was were which with
    will not no any all per than then they them these those such may can shall must should would could been being also
    other into out over upon about between during after before above below within without whether who whom whose what
    when where why how one two three four five six seven eight nine ten following given required calculate compute state
    explain discuss determine ltd limited company year years amount rs cost""".split()
)
_TOKEN = re.compile(r"[a-z][a-z0-9]+")
NAME_WEIGHT = 3.0
TOPIC_WEIGHT = 1.0
TITLE_HINT_WEIGHT = 4.0


@dataclass(frozen=True)
class ChapterDef:
    key: str
    name: str
    topics: tuple[str, ...] = ()


@dataclass(frozen=True)
class Classification:
    chapter_key: str
    confidence: float  # 0..1
    runner_up: str | None = None
    evidence: tuple[str, ...] = ()

    @property
    def is_confident(self) -> bool:
        return self.confidence >= 0.5


def _stem(word: str) -> str:
    for suffix in ("ations", "ation", "ings", "ing", "ies", "ed", "es", "s"):
        if word.endswith(suffix) and len(word) - len(suffix) >= 4:
            return word[: -len(suffix)]
    return word


def tokens(text: str) -> list[str]:
    return [_stem(t) for t in _TOKEN.findall((text or "").lower()) if t not in _STOP and len(t) > 2]


class ChapterIndex:
    """Weighted vocabulary of every chapter of one paper."""

    def __init__(self, chapters: list[ChapterDef]) -> None:
        self.chapters = chapters
        raw: list[Counter[str]] = []
        for ch in chapters:
            vocab: Counter[str] = Counter()
            for tok in tokens(ch.name):
                vocab[tok] += NAME_WEIGHT
            for topic in ch.topics:
                for tok in tokens(topic):
                    vocab[tok] += TOPIC_WEIGHT
            raw.append(vocab)
        frequency: Counter[str] = Counter()
        for vocab in raw:
            frequency.update(vocab.keys())
        n = max(1, len(chapters))
        self.vocab = [
            {tok: weight * (1.0 + math.log(n / frequency[tok])) for tok, weight in vocab.items()} for vocab in raw
        ]

    def scores(self, text: str, *, title_hint: str = "") -> list[float]:
        counts = Counter(tokens(text))
        hint = Counter(tokens(title_hint))
        out: list[float] = []
        for vocab in self.vocab:
            total = 0.0
            for tok, weight in vocab.items():
                if tok in counts:
                    total += weight * (1.0 + math.log(counts[tok]))
                if tok in hint:
                    total += weight * TITLE_HINT_WEIGHT
            out.append(total)
        return out


def _classification(index: ChapterIndex, scores: list[float], pick: int | None = None) -> Classification:
    ranked = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
    best = ranked[0] if pick is None else pick
    top = scores[best]
    others = [scores[i] for i in ranked if i != best]
    second = max(others) if others else 0.0
    if top <= 0:
        confidence = 0.0
    else:
        confidence = max(0.0, min(1.0, (top - second) / top)) * min(1.0, top / 6.0)
    runner = next((index.chapters[i].key for i in ranked if i != best and scores[i] > 0), None)
    return Classification(index.chapters[best].key, round(confidence, 2), runner)


def classify(index: ChapterIndex, text: str, *, title_hint: str = "") -> Classification:
    scores = index.scores(text, title_hint=title_hint)
    if not any(scores):
        return Classification(index.chapters[0].key, 0.0)
    return _classification(index, scores)


def classify_sequence(
    index: ChapterIndex,
    texts: list[str],
    *,
    forward_cost: float = 0.35,
    backward_cost: float = 0.9,
) -> list[Classification]:
    """Best chapter for each text in order, assuming the list roughly follows syllabus order."""
    n_ch = len(index.chapters)
    if not texts:
        return []
    raw = [index.scores(t) for t in texts]
    emission: list[list[float]] = []
    for row in raw:
        peak = max(row)
        emission.append([(v / peak) if peak > 0 else 0.0 for v in row])

    best = [[0.0] * n_ch for _ in texts]
    back = [[0] * n_ch for _ in texts]
    best[0] = list(emission[0])
    for t in range(1, len(texts)):
        for c in range(n_ch):
            candidates = []
            for p in range(n_ch):
                cost = 0.0 if p == c else (forward_cost if c > p else backward_cost)
                candidates.append(best[t - 1][p] - cost)
            p_best = max(range(n_ch), key=lambda p: candidates[p])
            best[t][c] = candidates[p_best] + emission[t][c]
            back[t][c] = p_best
    path = [0] * len(texts)
    path[-1] = max(range(n_ch), key=lambda c: best[-1][c])
    for t in range(len(texts) - 1, 0, -1):
        path[t - 1] = back[t][path[t]]

    results: list[Classification] = []
    for t, chosen in enumerate(path):
        base = _classification(index, raw[t], pick=chosen)
        if not any(raw[t]):
            results.append(Classification(base.chapter_key, 0.0, base.runner_up))  # carried from neighbours only
        else:
            own_best = max(range(n_ch), key=lambda c: raw[t][c])
            agree = (
                1.0 if own_best == chosen else 0.6 * (raw[t][chosen] / raw[t][own_best]) if raw[t][own_best] else 0.0
            )
            results.append(Classification(base.chapter_key, round(base.confidence * agree, 2), base.runner_up))
    return results
