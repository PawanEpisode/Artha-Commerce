"""
Which chapter a mark on a PDF page belongs to (FR-F03-30), pure. TypeScript twin: `lib/chapter-inheritance.ts`, shared
fixture `tests/fixtures/inheritance_cases.json`.

A mark carries the chapter its student chose (`explicit`), else the one the document maps its page to (`range`), else the
document's default chapter (`document`), else none. Why a function and not just SQL: the web shows the chip before the write
is accepted (offline), and the service re-links inherited marks when ranges change; both must agree. Explicit links are never
overwritten by a range change, which is why `source` is returned and stored (`notes_annotation.chapter_source`).

A "chapter reference" is opaque here (an id string, a key, a dict): this module never looks inside it. Matching outline
titles to real chapters is the service's job; `ranges_from_outline` only proposes page ranges.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

SOURCES = ("explicit", "range", "document", "none")


def effective_link(
    page: int, explicit_chapter: Any, ranges: Sequence[dict[str, Any]], document_default: Any
) -> tuple[Any, str]:
    """`(chapter_ref, source)` for a mark on `page`. Ranges are `{page_from, page_to, chapter}`, inclusive; the first match wins."""
    if explicit_chapter is not None:
        return explicit_chapter, "explicit"
    for r in ranges:
        if r["page_from"] <= page <= r["page_to"] and r.get("chapter") is not None:
            return r["chapter"], "range"
    if document_default is not None:
        return document_default, "document"
    return None, "none"


def _is_int(v: Any) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def validate_ranges(ranges: Sequence[dict[str, Any]]) -> dict[str, Any] | None:
    """
    None when the ranges are usable, else the first problem as `{"code", "a", "b"}` with indexes into `ranges`:
    `invalid_range` (not whole pages, or `1 <= page_from <= page_to` broken; `a == b`), else `overlap` between the two
    ranges that meet first when walking the pages in order (`a` reaches furthest, `b` starts inside it). The database
    refuses overlaps too (exclusion constraint); this gives the student the reason before the write.
    """
    for i, r in enumerate(ranges):
        if not (_is_int(r["page_from"]) and _is_int(r["page_to"]) and 1 <= r["page_from"] <= r["page_to"]):
            return {"code": "invalid_range", "a": i, "b": i}
    order = sorted(range(len(ranges)), key=lambda i: (ranges[i]["page_from"], ranges[i]["page_to"], i))
    furthest = None
    for k in order:
        if furthest is not None and ranges[k]["page_from"] <= ranges[furthest]["page_to"]:
            return {"code": "overlap", "a": furthest, "b": k}
        if furthest is None or ranges[k]["page_to"] > ranges[furthest]["page_to"]:
            furthest = k
    return None


def ranges_from_outline(outline: Sequence[dict[str, Any]], page_count: int) -> list[dict[str, Any]]:
    """
    Suggested page ranges from a PDF outline (`{title, page, children}`, pages 1-based): one range per top-level entry,
    from its page to the page before the next entry (the last one runs to `page_count`). Entries without a usable page, or
    pointing outside the document, are skipped; entries are taken in page order and a second entry on the same page is
    dropped (they cannot both own it). Pure: it does not match titles to chapters.
    """
    usable = [
        (e["page"], i, e.get("title", ""))
        for i, e in enumerate(outline)
        if _is_int(e.get("page")) and 1 <= e["page"] <= page_count
    ]
    usable.sort()
    entries: list[tuple[int, str]] = []
    for page, _, title in usable:
        if not entries or entries[-1][0] != page:
            entries.append((page, title))
    return [
        {"page_from": page, "page_to": (entries[k + 1][0] - 1) if k + 1 < len(entries) else page_count, "title": title}
        for k, (page, title) in enumerate(entries)
    ]
