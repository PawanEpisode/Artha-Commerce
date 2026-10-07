"""
Limits and safe-open helpers shared by the PDF worker libraries (ERD 6.5 and 7: untrusted files).

Safety model: files are parsed only here, in the worker. pikepdf (qpdf) and pypdfium2 (PDFium without V8 and without a form
environment) never execute JavaScript, launch actions or open URIs, and we never ask them to. Streams are not decoded
unless a caller renders or extracts, and rendering is guarded by `MAX_PAGE_POINTS` and `MAX_RENDER_PIXELS`.
"""

from __future__ import annotations

import hashlib
import os
import warnings
from collections.abc import Iterator
from contextlib import contextmanager

import pikepdf
import pypdfium2 as pdfium

MAX_PAGE_POINTS = 14_400  # 200 inches, the PDF 1.x limit for a page side
MAX_RENDER_PIXELS = 40_000_000  # a render bigger than this is a decompression bomb, not a page
MAX_PAGES = 1000
HEADER_WINDOW = 1024  # "%PDF-" must start within the first KB (no polyglots)


class PdfLimitError(Exception):
    """A file or page is over a hard limit (page count, page size, render pixels)."""


class PdfOpenError(Exception):
    """The file cannot be opened at all. `code` is a document status reason (`pdf_corrupt`, `decode_failed`)."""

    def __init__(self, message: str, code: str = "pdf_corrupt"):
        super().__init__(message)
        self.code = code


class PdfPasswordRequired(PdfOpenError):
    def __init__(self, message: str = "The file needs a password."):
        super().__init__(message, "password_required")


def sha256_file(path: str | os.PathLike, *, chunk_size: int = 1024 * 1024) -> str:
    """Hex SHA-256 of a file, streamed so a 100 MB PDF never sits in memory."""
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        while block := fh.read(chunk_size):
            digest.update(block)
    return digest.hexdigest()


def is_pdf_header(first_bytes: bytes) -> bool:
    """True when `%PDF-` appears within the first 1 KB. Anything later is a polyglot or a different format."""
    return b"%PDF-" in bytes(first_bytes)[:HEADER_WINDOW]


def file_has_pdf_header(path: str | os.PathLike) -> bool:
    with open(path, "rb") as fh:
        return is_pdf_header(fh.read(HEADER_WINDOW))


@contextmanager
def open_pikepdf(path: str | os.PathLike, *, password: str | None = None) -> Iterator[pikepdf.Pdf]:
    """
    Opens read-only for structure work. Raises `PdfPasswordRequired` for a missing or wrong user password and `PdfOpenError`
    for anything qpdf cannot parse even after its own recovery. The source file is never written.
    """
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            pdf = pikepdf.open(os.fspath(path), password=password or "", suppress_warnings=True)
    except pikepdf.PasswordError as exc:
        raise PdfPasswordRequired() from exc
    except (pikepdf.PdfError, OSError, ValueError, RuntimeError) as exc:
        raise PdfOpenError("The file could not be parsed.", "pdf_corrupt") from exc
    try:
        yield pdf
    finally:
        pdf.close()


@contextmanager
def open_pdfium(path: str | os.PathLike, *, password: str | None = None) -> Iterator[pdfium.PdfDocument]:
    """PDFium document for text and rendering. No form environment is initialised, so no scripts or actions can run."""
    try:
        doc = pdfium.PdfDocument(os.fspath(path), password=password)
    except pdfium.PdfiumError as exc:
        text = str(exc).lower()
        if "password" in text:
            raise PdfPasswordRequired() from exc
        raise PdfOpenError("The file could not be decoded.", "decode_failed") from exc
    try:
        yield doc
    finally:
        doc.close()


def inherited(page_obj: pikepdf.Object, key: str):
    """A page attribute that may be inherited from the /Pages tree (MediaBox, CropBox, Rotate, Resources)."""
    node = page_obj
    for _ in range(64):  # depth cap against a looping /Parent chain
        if key in node:
            return node[key]
        parent = node.get("/Parent")
        if parent is None:
            return None
        node = parent
    return None


def page_rotation(page_obj: pikepdf.Object) -> int:
    """Intrinsic /Rotate normalised to 0, 90, 180 or 270 (invalid values round to the nearest right angle)."""
    raw = inherited(page_obj, "/Rotate")
    try:
        value = int(raw) if raw is not None else 0
    except (TypeError, ValueError):
        return 0
    return (round(value / 90) * 90) % 360


def page_box(page_obj: pikepdf.Object) -> tuple[float, float, float, float]:
    """
    The visible box in user space as (x0, y0, x1, y1): the CropBox when present, clipped to the MediaBox, else the MediaBox
    (US Letter if the file has none, which the spec allows readers to assume).
    """

    def read(key: str):
        raw = inherited(page_obj, key)
        if raw is None:
            return None
        try:
            x0, y0, x1, y1 = (float(v) for v in raw)
        except (TypeError, ValueError):
            return None
        return (min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))

    media = read("/MediaBox") or (0.0, 0.0, 612.0, 792.0)
    crop = read("/CropBox")
    if crop is None:
        return media
    x0, y0, x1, y1 = max(crop[0], media[0]), max(crop[1], media[1]), min(crop[2], media[2]), min(crop[3], media[3])
    if x1 - x0 <= 0 or y1 - y0 <= 0:
        return media
    return (x0, y0, x1, y1)


def displayed_size(page_obj: pikepdf.Object) -> tuple[float, float, int]:
    """(width, height, rotation) in points of the page as displayed: crop box with the intrinsic /Rotate applied."""
    x0, y0, x1, y1 = page_box(page_obj)
    w, h = x1 - x0, y1 - y0
    rotation = page_rotation(page_obj)
    if rotation in (90, 270):
        w, h = h, w
    return w, h, rotation


def check_page_points(width: float, height: float) -> None:
    if width <= 0 or height <= 0 or max(width, height) > MAX_PAGE_POINTS:
        raise PdfLimitError(f"Page of {width:.0f} by {height:.0f} points is outside the allowed size.")


def check_render_pixels(width_pt: float, height_pt: float, scale: float) -> None:
    """Refuses a render before allocating it. `scale` is pixels per point."""
    if (width_pt * scale) * (height_pt * scale) > MAX_RENDER_PIXELS:
        raise PdfLimitError("The page would render to more than the allowed number of pixels.")
