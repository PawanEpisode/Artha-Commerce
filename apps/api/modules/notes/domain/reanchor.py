"""
Replace edition (PRD FR-F03-10, ERD decision 4), pure: where did each mark of the old edition go in the new one?

Text marks (highlight, underline) are found again by their quote (`anchoring`), on the same page first, then on the pages
around it, then anywhere. A mark with no text of its own (ink, area, text box, sticky note, bookmark) can only follow its page:
it moves when the page's text is the same in both editions and is otherwise listed for the student, because a drawing over
changed text may now be over the wrong words. Nothing is guessed: below `MIN_SCORE` the mark is "Needs attention".

Search cost is bounded: pages within `NEAR` of the old page get the full match (exact, then fuzzy); farther pages only an
exact match, so a 1,000-page edition does not run 1,000 fuzzy searches for a quote that is simply gone.
"""

from __future__ import annotations

import difflib
import re
from collections.abc import Callable
from dataclasses import dataclass

from . import anchoring

NEAR = 5  # pages either side of the old page that get the fuzzy search too
GOOD = 0.95  # a score at or above this ends the search at the nearest such page
ATTACH_MIN = 0.8  # below this a found quote is only offered to the student ("Needs attention"), never attached
SAME_PAGE_RATIO = 0.97  # text similarity at which a page counts as unchanged
SAME_PLACE_TOLERANCE = 0.01  # a found highlight within this of the old one (fractions of the page) keeps its old shape
NAMESPACE_NOTE = "notes.reanchor.v1"

TEXT_KINDS = frozenset({"highlight", "underline"})
Rect = list[float]


@dataclass(frozen=True)
class Found:
    page: int
    start: int
    end: int
    score: float


def page_order(hint_page: int, page_count: int) -> list[int]:
    """Pages nearest the old page first: 5, 4, 6, 3, 7 ..."""
    order = [hint_page] if 1 <= hint_page <= page_count else []
    for d in range(1, page_count + 1):
        for p in (hint_page - d, hint_page + d):
            if 1 <= p <= page_count:
                order.append(p)
    return order if order else list(range(1, page_count + 1))


def find_quote(
    quote: str,
    prefix: str,
    suffix: str,
    *,
    hint_page: int,
    hint_start: int | None,
    page_count: int,
    text_of: Callable[[int], str],
) -> Found | None:
    """
    The best place for the quote in the new edition. Stops at the nearest page with a good match; otherwise returns the
    best match over all pages (ties go to the nearer page), or None when nothing reaches `MIN_SCORE`.
    """
    best: Found | None = None
    for page in page_order(hint_page, page_count):
        near = abs(page - hint_page) <= NEAR
        text = text_of(page)
        hint = hint_start if page == hint_page else None
        locate = anchoring.locate_quote if near else anchoring.locate_exact
        hit = locate(text, quote, prefix, suffix, hint)
        if hit is None:
            continue
        found = Found(page, hit[0], hit[1], hit[2])
        if found.score >= GOOD:
            return found
        if best is None or found.score > best.score:
            best = found
    return best


_SPACE = re.compile(r"\s+")


def same_page_text(old: str, new: str) -> bool | None:
    """
    True when the page's words are unchanged (ignoring spacing and case), False when they differ, None when there is nothing to
    compare (a scan with no text: the marks cannot be checked, so they are listed instead of trusted).
    """
    a, b = _SPACE.sub(" ", old).strip().lower(), _SPACE.sub(" ", new).strip().lower()
    if len(a) < 20 or len(b) < 20:
        return None
    return difflib.SequenceMatcher(None, a, b, autojunk=False).ratio() >= SAME_PAGE_RATIO


def union(rects: list[Rect]) -> Rect:
    x0 = min(r[0] for r in rects)
    y0 = min(r[1] for r in rects)
    x1 = max(r[0] + r[2] for r in rects)
    y1 = max(r[1] + r[3] for r in rects)
    return [x0, y0, x1 - x0, y1 - y0]


def old_rects(kind: str, geometry: dict) -> list[Rect]:
    """The quads of a text mark's stored geometry (empty when it has none)."""
    quads = geometry.get("quads") if isinstance(geometry, dict) else None
    return [list(q) for q in quads] if isinstance(quads, list) else []


def same_place(old: list[Rect], new: list[Rect], tolerance: float = SAME_PLACE_TOLERANCE) -> bool:
    """True when the found text sits where the mark already is, so the stored shape (the student's own) is kept untouched."""
    if not old or not new:
        return False
    a, b = union(old), union(new)
    return all(abs(x - y) <= tolerance for x, y in zip(a, b, strict=True))
