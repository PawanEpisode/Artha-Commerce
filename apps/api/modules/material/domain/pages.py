"""
Locator and deep-link page calculation for F-12 Institute Study Material (ERD 2.3, PRD FR-F12-16).
"""

from __future__ import annotations

from urllib.parse import urldefrag


def format_deep_link(
    source_url: str | None,
    printed_page: int | None,
    page_offset: int = 0,
) -> str | None:
    """
    Constructs the exact deep link to an official PDF page:
    printed page N plus edition's page_offset.
    e.g. printed page 41 and offset 8 -> source_url#page=49
    """
    if not source_url:
        return None

    clean_url, _ = urldefrag(source_url)
    if printed_page is None:
        return clean_url

    target_page = max(1, printed_page + page_offset)
    return f"{clean_url}#page={target_page}"
