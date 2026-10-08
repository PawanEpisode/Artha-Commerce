"""
The new edition, read for Replace edition (R3): the raw text of a page (offsets match the text that was searched) and the
rectangles PDFium draws around a stretch of that text, in the stored frame of a mark (ERD 3.5: the page as displayed, origin
top-left, fractions of width and height, intrinsic /Rotate applied). The file is opened read-only and never written.

PDFium reports rectangles in user space (origin bottom-left of the page, the CropBox origin ignored). Like the export, which
runs the same maths the other way (`domain.coords.rect_to_user_space`), this moves them to the CropBox origin, turns y upside
down and then applies the page's own rotation.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager

import pypdfium2 as pdfium

from ..domain import coords
from ..domain.geometry import MAX_QUADS, MIN_QUAD_H, MIN_QUAD_W, merge_adjacent_quads, round5
from . import pdfutil

MAX_CACHED_PAGES = 400  # raw text kept in memory; farther pages are read again when asked for


class Edition:
    """A PDF opened for reading raw page text and quote rectangles."""

    def __init__(self, doc: pdfium.PdfDocument, pdf):
        self._doc, self._pdf = doc, pdf
        self.page_count = len(doc)
        self._text: dict[int, str] = {}

    def text(self, page: int) -> str:
        """Raw text of a 1-based page, as PDFium orders it (`""` for a page that cannot be read)."""
        if page in self._text:
            return self._text[page]
        out = ""
        try:
            pdf_page = self._doc[page - 1]
            try:
                pdfutil.check_page_points(*pdf_page.get_size())
                textpage = pdf_page.get_textpage()
                try:
                    out = textpage.get_text_range()
                finally:
                    textpage.close()
            finally:
                pdf_page.close()
        except (pdfutil.PdfLimitError, pdfium.PdfiumError, ValueError, MemoryError):
            out = ""
        if len(self._text) >= MAX_CACHED_PAGES:
            self._text.pop(next(iter(self._text)))
        self._text[page] = out
        return out

    def quads(self, page: int, start: int, end: int) -> list[list[float]]:
        """Rectangles around `text(page)[start:end]` in the stored frame, merged per line. Empty when PDFium gives none."""
        raw = self._rects(page, start, end - start)
        quads = []
        for rect in raw:
            r = [round5(min(max(v, 0.0), 1.0)) for v in rect]
            r[2], r[3] = min(r[2], round5(1 - r[0])), min(r[3], round5(1 - r[1]))
            if r[2] >= MIN_QUAD_W and r[3] >= MIN_QUAD_H:
                quads.append(r)
        return merge_adjacent_quads(quads)[:MAX_QUADS]

    def _rects(self, page: int, start: int, count: int) -> list[list[float]]:
        pdf_page = self._doc[page - 1]
        try:
            textpage = pdf_page.get_textpage()
            try:
                found = [textpage.get_rect(i) for i in range(textpage.count_rects(start, count))]
            finally:
                textpage.close()
        finally:
            pdf_page.close()
        x0, y0, x1, y1 = pdfutil.page_box(self._pdf.pages[page - 1].obj)
        rotation = pdfutil.page_rotation(self._pdf.pages[page - 1].obj)
        box_w, box_h = x1 - x0, y1 - y0
        out = []
        for left, bottom, right, top in found:
            unrotated = [(left - x0) / box_w, (y1 - top) / box_h, (right - left) / box_w, (top - bottom) / box_h]
            out.append(coords.rotate_rect(unrotated, rotation))
        return out


@contextmanager
def open_edition(path: str | os.PathLike) -> Iterator[Edition]:
    with pdfutil.open_pikepdf(path) as pdf, pdfutil.open_pdfium(path) as doc:
        yield Edition(doc, pdf)
