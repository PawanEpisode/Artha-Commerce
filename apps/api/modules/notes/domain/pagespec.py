"""
Page selections such as `"1-40,50"` (OCR and export options), pure. Pages are 1-based. A spec is a comma separated list of
single pages and inclusive ranges; spaces are ignored; the result is sorted and without duplicates. Everything is validated
against the page count, because a request that names page 900 of a 300 page file is a mistake, not a clipped range.
"""

from __future__ import annotations

import re

MAX_SPEC_CHARS = 200
_ITEM = re.compile(r"^(\d{1,5})(?:-(\d{1,5}))?$")


class PageSpecError(ValueError):
    """`code` is one of `empty`, `too_long`, `syntax`, `reversed`, `out_of_range`."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def parse_pages(spec: str | None, page_count: int) -> list[int]:
    """The pages a spec names, ascending. None or a blank spec means every page. Raises `PageSpecError`."""
    if page_count < 1:
        raise PageSpecError("out_of_range", "This file has no pages.")
    if spec is None or not str(spec).strip():
        return list(range(1, page_count + 1))
    text = "".join(str(spec).split())
    if len(text) > MAX_SPEC_CHARS:
        raise PageSpecError("too_long", "That page selection is too long.")
    chosen: set[int] = set()
    for item in text.split(","):
        match = _ITEM.match(item)
        if match is None:
            raise PageSpecError("syntax", "Use pages like 1-40,50.")
        first = int(match.group(1))
        last = int(match.group(2)) if match.group(2) else first
        if last < first:
            raise PageSpecError("reversed", "A page range must go from the lower page to the higher.")
        if first < 1 or last > page_count:
            raise PageSpecError("out_of_range", f"Pages must be between 1 and {page_count}.")
        chosen.update(range(first, last + 1))
    return sorted(chosen)


def format_pages(pages) -> str:
    """The canonical spec of a page set: `[1, 2, 3, 50]` -> `"1-3,50"`. Empty for no pages."""
    ordered = sorted(set(pages))
    parts: list[str] = []
    start = prev = None
    for page in ordered:
        if start is None:
            start = prev = page
        elif page == prev + 1:
            prev = page
        else:
            parts.append(str(start) if start == prev else f"{start}-{prev}")
            start = prev = page
    if start is not None:
        parts.append(str(start) if start == prev else f"{start}-{prev}")
    return ",".join(parts)
