"""
One PDF page as a small JPEG for the AI reader (R3). The picture is made in memory and never written to the student's
storage; only the worker calls this. Limits mirror the OCR renderer so a hostile page cannot exhaust memory.
"""

from __future__ import annotations

import io
import os

import pypdfium2 as pdfium

from . import pdfutil

MAX_SIDE_PX = 1800
JPEG_QUALITY = 80
MIME = "image/jpeg"


class PageImageError(Exception):
    """The page could not be turned into a picture (too large, damaged). Only that page is affected."""


def render_page_jpeg(path: str | os.PathLike, number: int) -> bytes:
    with pdfutil.open_pdfium(path) as doc:
        if number < 1 or number > len(doc):
            raise PageImageError("page_out_of_range")
        page = doc[number - 1]
        try:
            width_pt, height_pt = page.get_size()
            try:
                pdfutil.check_page_points(width_pt, height_pt)
            except pdfutil.PdfLimitError as exc:
                raise PageImageError("page_too_large") from exc
            scale = min(MAX_SIDE_PX / max(width_pt, height_pt), 300 / 72)
            try:
                pdfutil.check_render_pixels(width_pt, height_pt, scale)
            except pdfutil.PdfLimitError as exc:
                raise PageImageError("render_too_large") from exc
            image = page.render(scale=scale, may_draw_forms=False, grayscale=True).to_pil()
        except (pdfium.PdfiumError, ValueError, MemoryError) as exc:
            raise PageImageError("render_failed") from exc
        finally:
            page.close()
    try:
        buffer = io.BytesIO()
        image.convert("L").save(buffer, format="JPEG", quality=JPEG_QUALITY)
        return buffer.getvalue()
    finally:
        image.close()
