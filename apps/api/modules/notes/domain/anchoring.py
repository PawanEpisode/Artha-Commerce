"""
Text anchoring (ERD decision 4), pure: find a highlighted quote again in page text that has changed shape. TypeScript twin:
`web/src/modules/notes/lib/anchors.ts`; both read `tests/fixtures/anchoring_cases.json`, so the algorithm below is the
contract and must be ported line by line, never "improved" on one side only.

Why: pdf.js (in the browser) and PDFium (in the worker) order and space the same page's text differently, OCR output
changes between engine versions, and Replace edition (R3) swaps the file. Offsets break; the quote survives. So a mark
stores `quote_exact`, 32 characters of prefix and suffix, and offsets that are only hints.

1. `normalise_for_match(text)`: per cluster (a character plus its combining marks): NFKC, lower case, drop soft hyphens and
   zero-width characters, collapse any whitespace run to one space, and join a word broken by a hyphen at the end of a line
   ("deduc-\\ntion" becomes "deduction", only when a lower-case or caseless letter follows, so "Section 17-\\nA" stays). It
   keeps `starts`/`ends`: for each normalised character the span of the original it came from, to map a match back.
2. `make_selector(page_text, start, end)`: the stored quote fields from a selection.
3. `locate_quote(...)` on normalised text (quote stripped of outer spaces):
   a. Exact: every occurrence. With several, rank by context (how many characters of prefix and suffix agree, as a share),
      then by distance to the hint, then by position. Score 1.0, or 0.75 when the choice was a tie (nothing separates them).
   b. Fuzzy (quote 8 to 300 characters, no exact hit): vote for where the quote's 4-grams occur (grams that occur more than
      20 times are ignored); a vote lands in a bucket of 16 characters by diagonal (page position minus quote position); take
      the three best buckets (not within 2 of one another, at least 2 votes). In each window (bucket start minus slack to
      bucket start plus quote length plus slack, slack = 40% of the quote + 2) run Sellers' approximate substring
      match (Levenshtein, free start, free end; ties prefer diagonal, then skipping a quote character, then skipping a
      page character; the start is carried along the best path). Accept at most 40% edits; score = 1 - edits / quote length.
      The best window is the fewest edits, then the best context, then nearest the hint, then earliest.
   c. Longer quotes (over 300): locate the first and the last 120 characters on their own and join them when the span is
      60% to 160% of the quote.
   Anything below `MIN_SCORE` (0.6) is "not found": the mark is kept and shown as detached rather than guessed.

Offsets are in code points here and UTF-16 units in the TypeScript twin: identical for Latin and Devanagari text (the whole
Basic Multilingual Plane), and only a hint for the rest.
"""

from __future__ import annotations

import unicodedata
from bisect import bisect_left
from dataclasses import dataclass

CONTEXT_CHARS = 32
MAX_QUOTE = 1000
MIN_SCORE = 0.6
MIN_FUZZY, MAX_FUZZY, LONG_PART = 8, 300, 120
GRAM, BUCKET, MAX_GRAM_HITS, MIN_VOTES, MAX_WINDOWS = 4, 16, 20, 2, 3

_DROPPED = frozenset({0xAD, 0x200B, 0x200C, 0x200D, 0x200E, 0x200F, 0x2060, 0xFEFF})
_HYPHENS = frozenset("-‐‑")
_SPACES = frozenset(
    [9, 10, 11, 12, 13, 32, 0x85, 0xA0, 0x1680, *range(0x2000, 0x200B), 0x2028, 0x2029, 0x202F, 0x205F, 0x3000]
)
_LINE_BREAKS = frozenset("\n\r  ")


@dataclass(frozen=True)
class Normalised:
    text: str
    starts: tuple[int, ...]  # original index where each normalised character begins
    ends: tuple[int, ...]  # original index just after it


def _clusters(text: str) -> list[tuple[int, int]]:
    out: list[tuple[int, int]] = []
    for i, ch in enumerate(text):
        if out and unicodedata.category(ch).startswith("M"):
            out[-1] = (out[-1][0], i + 1)
        else:
            out.append((i, i + 1))
    return out


def _fold(cluster: str) -> list[str]:
    return [c for c in unicodedata.normalize("NFKC", cluster).lower() if ord(c) not in _DROPPED]


def _is_space(c: str) -> bool:
    return ord(c) in _SPACES


def _join_after(clusters: list[tuple[int, int]], text: str, i: int) -> int | None:
    """If the hyphen at cluster `i` ends a line inside a word, the index of the cluster where the word continues."""
    j, saw_break = i + 1, False
    while j < len(clusters):
        chunk = text[clusters[j][0] : clusters[j][1]]
        if ord(chunk[0]) in _DROPPED or _is_space(chunk[0]):
            saw_break = saw_break or chunk[0] in _LINE_BREAKS
            j += 1
        else:
            return j if saw_break and unicodedata.category(chunk[0]) in ("Ll", "Lo", "Lm") else None
    return None


def normalise_for_match(text: str) -> Normalised:
    clusters = _clusters(text)
    chars: list[str] = []
    starts: list[int] = []
    ends: list[int] = []
    i = 0
    while i < len(clusters):
        s, e = clusters[i]
        chunk = text[s:e]
        if chunk in _HYPHENS and chars and chars[-1] != " " and unicodedata.category(chars[-1])[0] in "LM":
            joined = _join_after(clusters, text, i)
            if joined is not None:
                i = joined
                continue
        for c in _fold(chunk):
            if _is_space(c):
                if chars and chars[-1] == " ":
                    ends[-1] = e
                else:
                    chars.append(" ")
                    starts.append(s)
                    ends.append(e)
            else:
                chars.append(c)
                starts.append(s)
                ends.append(e)
        i += 1
    return Normalised("".join(chars), tuple(starts), tuple(ends))


def make_selector(page_text: str, start: int, end: int) -> dict[str, object]:
    """The quote fields stored on a mark for the selection `page_text[start:end]`."""
    start, end = max(0, start), min(len(page_text), end)
    if start >= end:
        raise ValueError("empty selection")
    return {
        "quote_exact": page_text[start:end][:MAX_QUOTE],
        "quote_prefix": page_text[max(0, start - CONTEXT_CHARS) : start],
        "quote_suffix": page_text[end : end + CONTEXT_CHARS],
        "text_start": start,
        "text_end": end,
    }


def _score(x: float) -> float:
    return int(x * 10_000 + 0.5) / 10_000


def _common_suffix(a: str, b: str) -> int:
    n = 0
    while n < len(a) and n < len(b) and a[-1 - n] == b[-1 - n]:
        n += 1
    return n


def _common_prefix(a: str, b: str) -> int:
    n = 0
    while n < len(a) and n < len(b) and a[n] == b[n]:
        n += 1
    return n


def _context(text: str, a: int, b: int, prefix: str, suffix: str) -> float:
    """Share of the stored prefix (read backwards) and suffix that agree with the text around [a, b); 0 to 1."""
    pre, suf = prefix.rstrip(" "), suffix.lstrip(" ")
    parts = []
    if pre:
        parts.append(min(1.0, _common_suffix(pre, text[:a].rstrip(" ")) / len(pre)))
    if suf:
        parts.append(min(1.0, _common_prefix(suf, text[b:].lstrip(" ")) / len(suf)))
    return sum(parts) / len(parts) if parts else 0.0


def _exact(text: str, q: str, pre: str, suf: str, hint: int | None):
    found, i = [], text.find(q)
    while i != -1:
        found.append(i)
        i = text.find(q, i + 1)
    if not found:
        return None
    ranked = sorted(
        (-_context(text, i, i + len(q), pre, suf), abs(i - hint) if hint is not None else 0, i) for i in found
    )
    tie = len(ranked) > 1 and ranked[0][:2] == ranked[1][:2]
    return ranked[0][2], ranked[0][2] + len(q), 0.75 if tie else 1.0


def _windows(text: str, q: str) -> list[tuple[int, int]]:
    m = len(q)
    wanted = {q[i : i + GRAM] for i in range(m - GRAM + 1)}
    hits: dict[str, list[int]] = {}
    for i in range(len(text) - GRAM + 1):
        g = text[i : i + GRAM]
        if g in wanted:
            hits.setdefault(g, []).append(i)
    votes: dict[int, int] = {}
    for qi in range(m - GRAM + 1):
        positions = hits.get(q[qi : qi + GRAM], [])
        if len(positions) <= MAX_GRAM_HITS:
            for pi in positions:
                bucket = (pi - qi) // BUCKET
                votes[bucket] = votes.get(bucket, 0) + 1
    chosen: list[int] = []
    for bucket, n in sorted(votes.items(), key=lambda kv: (-kv[1], kv[0])):
        if n >= MIN_VOTES and all(abs(bucket - c) > 2 for c in chosen):
            chosen.append(bucket)
            if len(chosen) == MAX_WINDOWS:
                break
    slack = m * 2 // 5 + 2
    return [(max(0, b * BUCKET - slack), min(len(text), b * BUCKET + BUCKET + m + slack)) for b in chosen]


def _sellers(q: str, t: str) -> tuple[int, int, int]:
    """Best approximate occurrence of `q` in `t`: (edits, start, end). Ties as described in the module docstring."""
    n = len(t)
    cost, start = [0] * (n + 1), list(range(n + 1))
    for i in range(1, len(q) + 1):
        cur_cost, cur_start = [i] + [0] * n, [0] * (n + 1)
        for j in range(1, n + 1):
            best, st = cost[j - 1] + (0 if q[i - 1] == t[j - 1] else 1), start[j - 1]
            if cost[j] + 1 < best:
                best, st = cost[j] + 1, start[j]
            if cur_cost[j - 1] + 1 < best:
                best, st = cur_cost[j - 1] + 1, cur_start[j - 1]
            cur_cost[j], cur_start[j] = best, st
        cost, start = cur_cost, cur_start
    end = min(range(n + 1), key=lambda j: (cost[j], j))
    return cost[end], start[end], end


def _trim(text: str, a: int, b: int) -> tuple[int, int]:
    while a < b and text[a] == " ":
        a += 1
    while b > a and text[b - 1] == " ":
        b -= 1
    return a, b


def _fuzzy(text: str, q: str, pre: str, suf: str, hint: int | None):
    m = len(q)
    if m < MIN_FUZZY:
        return None
    best = None
    for lo, hi in _windows(text, q):
        edits, s, e = _sellers(q, text[lo:hi])
        if edits > m * 2 // 5:
            continue
        a, b = _trim(text, lo + s, lo + e)
        if a >= b:
            continue
        key = (edits, -_context(text, a, b, pre, suf), abs(a - hint) if hint is not None else 0, a)
        if best is None or key < best[0]:
            best = (key, a, b, 1 - edits / m)
    return None if best is None else (best[1], best[2], _score(best[3]))


def _locate(text: str, q: str, pre: str, suf: str, hint: int | None):
    exact = _exact(text, q, pre, suf, hint)
    if exact:
        return exact
    if len(q) <= MAX_FUZZY:
        return _fuzzy(text, q, pre, suf, hint)
    head = _locate(text, q[:LONG_PART], pre, "", hint)
    tail = _locate(text, q[-LONG_PART:], "", suf, hint)
    if not head or not tail or tail[1] <= head[0]:
        return None
    span = tail[1] - head[0]
    return (head[0], tail[1], _score(min(head[2], tail[2]))) if 0.6 * len(q) <= span <= 1.6 * len(q) else None


def locate_quote(
    page_text: str, quote_exact: str, prefix: str = "", suffix: str = "", hint_start: int | None = None
) -> tuple[int, int, float] | None:
    """
    Where the quote is now: `(start, end, score)` as offsets into `page_text` (the original text, not the normalised one),
    or None when nothing scores at least `MIN_SCORE`. `hint_start` is the stored `text_start`, used only to break ties.
    """
    page = normalise_for_match(page_text)
    q = normalise_for_match(quote_exact).text.strip(" ")
    if not q or not page.text:
        return None
    pre, suf = normalise_for_match(prefix).text, normalise_for_match(suffix).text
    hint = None if hint_start is None else bisect_left(page.starts, hint_start)
    found = _locate(page.text, q, pre, suf, hint)
    if found is None or found[2] < MIN_SCORE:
        return None
    a, b, score = found
    return page.starts[a], page.ends[b - 1], score


def locate_exact(
    page_text: str, quote_exact: str, prefix: str = "", suffix: str = "", hint_start: int | None = None
) -> tuple[int, int, float] | None:
    """
    Server-only shortcut (no TypeScript twin, the shared algorithm is untouched): step (a) of `locate_quote` alone, for the
    many pages of a new edition where only an exact hit is worth looking for. Same offsets and score as `locate_quote` would
    give when the quote occurs exactly.
    """
    page = normalise_for_match(page_text)
    q = normalise_for_match(quote_exact).text.strip(" ")
    if not q or q not in page.text:
        return None
    pre, suf = normalise_for_match(prefix).text, normalise_for_match(suffix).text
    hint = None if hint_start is None else bisect_left(page.starts, hint_start)
    found = _exact(page.text, q, pre, suf, hint)
    if not found:
        return None
    a, b, score = found
    return page.starts[a], page.ends[b - 1], score
