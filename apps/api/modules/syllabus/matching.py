"""
Name matching used to propose chapter maps between two schemes of a level, and to carry topics over by name.

Pure functions only: no database access, so every rule here is covered by plain unit tests. The service layer
(`services.build_default_chapter_map`) feeds it chapters and stores what it proposes.

How a proposal is made, per paper, in this order (each step only looks at what the earlier steps left over):

1. Same key: the original rule. Marked for review when the names have nothing in common (a re-used key).
2. Same normalised name, or a near-identical one. "Chapter 3: Income from Salaries" and "3. Income from Salary"
   count as the same name; between equally close candidates the one at the nearer position in the paper wins.
3. Merge and split: a new chapter whose name contains two or more old chapter names is a merge, an old chapter
   whose name contains two or more new chapter names is a split. Always flagged for review. Then the remaining
   related-but-not-identical names are paired and flagged.
4. Renamed in place: the one chapter left on each side of a paper is paired when the names still resemble each other.

Papers are paired by key, then by name. Chapters still unmatched after that are tried across papers (a chapter
that moved paper), also flagged for review.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from decimal import Decimal
from difflib import SequenceMatcher

HIGH = 0.85  # at or above: trusted without review
LOW = 0.60  # at or above: proposed, but an editor must confirm
RELATED = (
    0.50  # names this close are "related": below it a re-used key is suspect and a lone leftover pair is not paired
)
SUBJECT_FLOOR = 0.75  # paper names must be this close to be paired when the keys differ
MOVED_FLOOR = 0.90  # across papers only near-identical names are proposed
CONTAINS = 0.80  # share of a name's words that must appear in the other name for split and merge
ORDER_BONUS = 0.04  # a perfect position match adds this much to a name score when ranking candidates

_STOP = frozenset({"a", "an", "and", "of", "the", "in", "on", "for", "to", "with", "or", "as", "at", "by"})
_LEADING_NUMBER = re.compile(
    r"""^\s*(?:
        (?:chapter|unit|module|part|section|ch|lesson|topic)\s*\d+(?:\.\d+)*[a-z]?\s*[:.)\-\u2013\u2014]?\s*  # Chapter 3: / Unit 4 -
      | \d+(?:\.\d+)+[a-z]?\s*[:.)\-\u2013\u2014]?\s*                                                  # 2.1  3.4.2
      | \d+[a-z]?\s*[:.)\-\u2013\u2014]\s*                                                               # 3.  3)  3:  3 -
    )""",
    re.IGNORECASE | re.VERBOSE,
)


def normalise(name: str) -> str:
    """Lower-case words only: accents, punctuation, '&', leading numbering ('Chapter 3:', '2.1') and spacing removed."""
    text = unicodedata.normalize("NFKD", name or "")
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.replace("&", " and ")
    text = _LEADING_NUMBER.sub("", text.strip())
    text = re.sub(r"[^0-9a-zA-Z]+", " ", text).lower()
    return " ".join(text.split())


def _stem(word: str) -> str:
    if len(word) > 4 and word.endswith("ies"):
        return word[:-3] + "y"
    if len(word) > 4 and word.endswith(("sses", "xes", "ches", "shes")):
        return word[:-2]
    if len(word) > 3 and word.endswith("s") and not word.endswith("ss"):
        return word[:-1]
    return word


def tokens(name: str) -> frozenset[str]:
    """The meaningful words of a name (stop words dropped, plurals folded)."""
    return frozenset(_stem(w) for w in normalise(name).split() if w not in _STOP)


def similarity(a: str, b: str) -> float:
    """0 to 1. 1.0 means the normalised names are identical."""
    na, nb = normalise(a), normalise(b)
    if not na or not nb:
        return 0.0
    if na == nb:
        return 1.0
    ta, tb = tokens(a), tokens(b)
    ratio = SequenceMatcher(None, na, nb).ratio()
    jaccard = len(ta & tb) / len(ta | tb) if ta and tb else 0.0
    return round(max(ratio, jaccard), 4)


def contained_share(inner: str, outer: str) -> float:
    """Share of the words of `inner` that also appear in `outer`."""
    ti, to = tokens(inner), tokens(outer)
    return len(ti & to) / len(ti) if ti else 0.0


@dataclass(frozen=True)
class Item:
    """A chapter or paper as the matcher sees it. `ref` is whatever the caller wants back (an id or object)."""

    ref: object
    key: str
    name: str
    position: int = 0  # index inside its parent


@dataclass(frozen=True)
class Proposal:
    old: object
    new: object
    relation: str  # same | split | merged
    basis: str  # key | name | fuzzy | renamed | moved | split | merge
    confidence: float
    needs_review: bool
    carry_ratio: Decimal = Decimal("1.00")


@dataclass
class MatchResult:
    proposals: list[Proposal] = field(default_factory=list)
    unmatched_old: list[Item] = field(default_factory=list)
    unmatched_new: list[Item] = field(default_factory=list)


def _relative(position: int, total: int) -> float:
    return position / (total - 1) if total > 1 else 0.0


def _ratio(count: int) -> Decimal:
    return (Decimal(1) / Decimal(count)).quantize(Decimal("0.01"))


def _union_share(whole: Item, parts: list[Item]) -> float:
    """How much of the words of `whole` the `parts` together account for."""
    words = tokens(whole.name)
    covered = set().union(*(tokens(p.name) for p in parts)) & words
    return len(covered) / len(words) if words else 0.0


def _pair_by_name(
    left_old: list[Item],
    left_new: list[Item],
    old: list[Item],
    new: list[Item],
    proposals: list[Proposal],
    *,
    low: float,
) -> None:
    """Greedy 1:1 pairing of the remaining chapters whose names score at least `low`, best score (then position) first."""
    candidates: list[tuple[float, float, Item, Item]] = []
    for o in left_old:
        for n in left_new:
            score = similarity(o.name, n.name)
            if score >= low:
                near = 1 - abs(_relative(o.position, len(old)) - _relative(n.position, len(new)))
                candidates.append((score + ORDER_BONUS * near, score, o, n))
    candidates.sort(key=lambda c: (-c[0], c[2].position, c[3].position))
    for _, score, o, n in candidates:
        if o not in left_old or n not in left_new:
            continue
        exact = score == 1.0
        proposals.append(
            Proposal(
                o.ref,
                n.ref,
                "same",
                "name" if exact else "fuzzy",
                0.95 if exact else score,
                (not exact) and score < HIGH,
            )
        )
        left_old.remove(o)
        left_new.remove(n)


def match_chapters(old: list[Item], new: list[Item]) -> MatchResult:
    """Proposes how the chapters of one old paper carry into one new paper. See the module docstring."""
    proposals: list[Proposal] = []
    left_old = list(old)
    left_new = list(new)

    # 1. same key
    by_key = {n.key: n for n in left_new}
    for o in list(left_old):
        n = by_key.get(o.key)
        if n is None or n not in left_new:
            continue
        reused = similarity(o.name, n.name) < RELATED
        proposals.append(Proposal(o.ref, n.ref, "same", "key", 0.4 if reused else 1.0, reused))
        left_old.remove(o)
        left_new.remove(n)

    # 2. the same name (or a near-identical one), nearest position first
    _pair_by_name(left_old, left_new, old, new, proposals, low=HIGH)

    # 3a. merges: one new chapter that contains the names of several old ones
    for n in list(left_new):
        parts = [o for o in left_old if len(tokens(o.name)) >= 2 and contained_share(o.name, n.name) >= CONTAINS]
        if 2 <= len(parts) <= 4 and _union_share(n, parts) >= 0.5:
            ratio = _ratio(len(parts))
            for o in parts:
                proposals.append(Proposal(o.ref, n.ref, "merged", "merge", 0.7, True, ratio))
                left_old.remove(o)
            left_new.remove(n)

    # 3b. splits: one old chapter that contains the names of several new ones
    for o in list(left_old):
        parts = [n for n in left_new if len(tokens(n.name)) >= 2 and contained_share(n.name, o.name) >= CONTAINS]
        if 2 <= len(parts) <= 4 and _union_share(o, parts) >= 0.5:
            for n in parts:
                proposals.append(Proposal(o.ref, n.ref, "split", "split", 0.7, True))
                left_new.remove(n)
            left_old.remove(o)

    # 3b2. closer-than-not names: related but not identical, flagged for review
    _pair_by_name(left_old, left_new, old, new, proposals, low=LOW)

    # 4. renamed in place: the only chapter left on each side
    if len(left_old) == 1 and len(left_new) == 1:
        o, n = left_old[0], left_new[0]
        score = similarity(o.name, n.name)
        if score >= RELATED:
            proposals.append(Proposal(o.ref, n.ref, "same", "renamed", score, True))
            left_old, left_new = [], []

    return MatchResult(proposals, left_old, left_new)


def match_papers(old: list[Item], new: list[Item]) -> list[tuple[Item, Item]]:
    """Pairs papers by key, then by identical or close name. Each paper is used once."""
    pairs: list[tuple[Item, Item]] = []
    left_old, left_new = list(old), list(new)
    by_key = {n.key: n for n in left_new}
    for o in list(left_old):
        n = by_key.get(o.key)
        if n is not None and n in left_new:
            pairs.append((o, n))
            left_old.remove(o)
            left_new.remove(n)
    scored = sorted(
        ((similarity(o.name, n.name), o, n) for o in left_old for n in left_new),
        key=lambda t: (-t[0], t[1].position, t[2].position),
    )
    for score, o, n in scored:
        if score >= SUBJECT_FLOOR and o in left_old and n in left_new:
            pairs.append((o, n))
            left_old.remove(o)
            left_new.remove(n)
    return pairs


def match_moved(old: list[Item], new: list[Item]) -> list[Proposal]:
    """Chapters left over in unrelated papers: near-identical names are taken as a chapter that moved paper."""
    proposals: list[Proposal] = []
    left_new = list(new)
    scored = sorted(
        ((similarity(o.name, n.name), o, n) for o in old for n in new),
        key=lambda t: (-t[0], t[1].position, t[2].position),
    )
    used_old: set[int] = set()
    for score, o, n in scored:
        if score < MOVED_FLOOR:
            break
        if id(o) in used_old or n not in left_new:
            continue
        proposals.append(Proposal(o.ref, n.ref, "same", "moved", min(score, 0.8), True))
        used_old.add(id(o))
        left_new.remove(n)
    return proposals
