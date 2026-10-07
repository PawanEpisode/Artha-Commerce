"""
`extract_pages`: native text per page through PDFium (ERD 6.5 Extract job). One bad page never aborts a chunk.

Normalisation: NUL and other control characters removed, each run of whitespace becomes one space, or one newline when
the run contained a line break, at most 60,000 characters per page.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass

import pypdfium2 as pdfium

from . import pdfutil

MAX_CHARS_PER_PAGE = 60_000
DEFAULT_CHUNK = 20

_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f￾￿]")
_WS_RUN = re.compile(r"\s+")
_DEVANAGARI = re.compile(r"[ऀ-ॿ꣠-ꣿ]")
_LATIN = re.compile(r"[A-Za-z]")


@dataclass(frozen=True)
class PageText:
    page: int  # 1-based
    text: str
    chars: int
    lang_hint: str | None = None  # "hi" when Devanagari dominates the letters, "en" when Latin does, else None
    error: str | None = None


def chunk_ranges(page_count: int, size: int = DEFAULT_CHUNK) -> list[tuple[int, int]]:
    """1-based inclusive (from, to) ranges covering 1..page_count in pieces of `size`. Empty for no pages."""
    if size < 1:
        raise ValueError("size must be at least 1")
    return [(start, min(start + size - 1, page_count)) for start in range(1, page_count + 1, size)]


def normalise_text(raw: str) -> str:
    cleaned = _CONTROL.sub("", raw)
    cleaned = _WS_RUN.sub(lambda m: "\n" if "\n" in m.group() or "\r" in m.group() else " ", cleaned).strip()
    return cleaned[:MAX_CHARS_PER_PAGE]


def lang_hint(text: str) -> str | None:
    hindi, latin = len(_DEVANAGARI.findall(text)), len(_LATIN.findall(text))
    if hindi == 0 and latin == 0:
        return None
    return "hi" if hindi >= latin else "en"


def extract_pages(
    path: str | os.PathLike, page_from: int, page_to: int, *, password: str | None = None
) -> list[PageText]:
    """
    Text of pages `page_from..page_to` (1-based, inclusive; `page_to` is clipped to the page count). Raises `PdfOpenError`
    when the whole file cannot be opened. A page that fails comes back with empty text and an `error` string.
    """
    if page_from < 1 or page_to < page_from:
        raise ValueError("Invalid page range.")
    results: list[PageText] = []
    with pdfutil.open_pdfium(path, password=password) as doc:
        last = min(page_to, len(doc))
        for number in range(page_from, last + 1):
            results.append(_extract_one(doc, number))
    return results


def _extract_one(doc: pdfium.PdfDocument, number: int) -> PageText:
    try:
        page = doc[number - 1]
        try:
            width, height = page.get_size()
            pdfutil.check_page_points(width, height)
            textpage = page.get_textpage()
            try:
                text = normalise_text(textpage.get_text_range())
            finally:
                textpage.close()
        finally:
            page.close()
    except pdfutil.PdfLimitError:
        return PageText(number, "", 0, None, "page_too_large")
    except (pdfium.PdfiumError, ValueError, MemoryError):
        return PageText(number, "", 0, None, "extract_failed")
    return PageText(number, text, len(text), lang_hint(text))
