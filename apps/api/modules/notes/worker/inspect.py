"""
`inspect_pdf`: everything the Inspect job (ERD 6.5) learns from a stored PDF, with no database and no network.

Order of work: header check, qpdf open (encryption, permissions, page tree), page boxes and outline from pikepdf, then
PDFium for the cover thumbnail and the native-text sample. A file that needs a user password returns `ok=True,
needs_password=True` and nothing about its pages: the password is typed in the browser and never reaches the worker in R2.
"""

from __future__ import annotations

import io
import os
from dataclasses import dataclass

import pikepdf
import pypdfium2 as pdfium

from . import pdfutil
from .pdfutil import PdfLimitError, PdfOpenError, PdfPasswordRequired

OUTLINE_MAX_NODES = 2000
OUTLINE_MAX_DEPTH = 12
OUTLINE_TITLE_MAX = 300
COVER_WIDTH_PX = 240
MIN_TEXT_CHARS = 20  # a sampled page with fewer extractable characters has no native text
SCANNED_SHARE = 0.70  # ERD 2.2: at least 70% of the sampled pages are image-only
COVER_PAGE_FRACTION = 0.6  # an image covering this share of the page area counts as "the page is a picture"


@dataclass(frozen=True)
class InspectResult:
    ok: bool
    error_code: str | None = None  # pdf_corrupt | too_many_pages | decode_failed | policy | type_mismatch
    is_encrypted: bool = False
    needs_password: bool = False
    page_count: int | None = None
    page_meta: tuple[dict, ...] = ()  # one {"w", "h"} per page, points, /Rotate applied, crop box if present
    outline: tuple[dict, ...] = ()  # [{"title", "page" (1-based or None), "children": [...]}], at most 2000 nodes
    can_copy: bool | None = None
    can_modify: bool | None = None
    has_javascript: bool = False
    is_scanned: bool | None = None
    text_pct: int | None = None  # share (0..100) of sampled pages with native text
    sha256: str | None = None
    bytes: int | None = None
    cover_webp: bytes | None = None
    engine_version: str = ""


def engine_version() -> str:
    return (
        f"pikepdf {pikepdf.__version__} (qpdf {pikepdf.__libqpdf_version__}); pypdfium2 {pdfium.version.PYPDFIUM_INFO}"
    )


def scanned_verdict(samples: list[tuple[int, bool]]) -> tuple[bool, int]:
    """
    `samples` is one (extractable characters, image covers the page) per sampled page. Returns (is_scanned, text_pct).
    Scanned means at least 70% of the sample has under 20 characters AND an image covering the page. This mirrors ERD 2.2;
    if `modules/notes/domain/ocr_quality.is_scanned` lands it should replace this function (one call site).
    """
    if not samples:
        return False, 0
    with_text = sum(1 for chars, _ in samples if chars >= MIN_TEXT_CHARS)
    picture_only = sum(1 for chars, covered in samples if chars < MIN_TEXT_CHARS and covered)
    return picture_only / len(samples) >= SCANNED_SHARE, round(100 * with_text / len(samples))


def sample_indices(page_count: int, sample_pages: int) -> list[int]:
    """Zero-based indexes spread evenly over the document (first and last included when there is room)."""
    n = max(1, min(sample_pages, page_count))
    if n == 1:
        return [0]
    return sorted({round(i * (page_count - 1) / (n - 1)) for i in range(n)})


def _fail(code: str, **known) -> InspectResult:
    return InspectResult(ok=False, error_code=code, engine_version=engine_version(), **known)


def inspect_pdf(path: str | os.PathLike, *, password: str | None = None, sample_pages: int = 20) -> InspectResult:
    try:
        size = os.path.getsize(path)
        sha = pdfutil.sha256_file(path)
    except OSError:
        return _fail("pdf_corrupt")
    known = {"bytes": size, "sha256": sha}
    if not pdfutil.file_has_pdf_header(path):
        return _fail("type_mismatch", **known)

    try:
        with pdfutil.open_pikepdf(path, password=password) as pdf:
            return _inspect_open(path, pdf, password, sample_pages, known)
    except PdfPasswordRequired:
        return InspectResult(ok=True, is_encrypted=True, needs_password=True, engine_version=engine_version(), **known)
    except PdfOpenError as exc:
        return _fail(exc.code, **known)
    except PdfLimitError:
        return _fail("policy", **known)


def _inspect_open(path, pdf: pikepdf.Pdf, password, sample_pages: int, known: dict) -> InspectResult:
    try:
        page_count = len(pdf.pages)
    except (pikepdf.PdfError, RuntimeError, ValueError):
        return _fail("pdf_corrupt", **known)
    if page_count == 0:
        return _fail("pdf_corrupt", **known)
    if page_count > pdfutil.MAX_PAGES:
        return _fail("too_many_pages", **known)

    page_meta: list[dict] = []
    try:
        for page in pdf.pages:
            w, h, _ = pdfutil.displayed_size(page.obj)
            pdfutil.check_page_points(w, h)
            page_meta.append({"w": round(w, 2), "h": round(h, 2)})
    except PdfLimitError:
        return _fail("policy", **known)
    except (pikepdf.PdfError, RuntimeError, ValueError):
        return _fail("pdf_corrupt", **known)

    allow = pdf.allow if pdf.is_encrypted else None
    try:
        with pdfutil.open_pdfium(path, password=password) as doc:
            if len(doc) != page_count:  # the two parsers disagree: trust neither
                return _fail("decode_failed", **known)
            cover = _cover_webp(doc)
            samples = _sample_text(doc, sample_indices(page_count, sample_pages))
    except PdfPasswordRequired:
        return InspectResult(ok=True, is_encrypted=True, needs_password=True, engine_version=engine_version(), **known)
    except PdfOpenError as exc:
        return _fail(exc.code, **known)

    is_scanned, text_pct = scanned_verdict(samples)
    return InspectResult(
        ok=True,
        is_encrypted=bool(pdf.is_encrypted),
        page_count=page_count,
        page_meta=tuple(page_meta),
        outline=tuple(_outline(pdf, page_count)),
        can_copy=True if allow is None else bool(allow.extract),
        can_modify=True if allow is None else bool(allow.modify_other),
        has_javascript=_has_javascript(pdf),
        is_scanned=is_scanned,
        text_pct=text_pct,
        cover_webp=cover,
        engine_version=engine_version(),
        **known,
    )


# --- thumbnail and text sample (PDFium) -----------------------------------------------------------------------------


def _cover_webp(doc: pdfium.PdfDocument) -> bytes | None:
    """First page at 240 px wide as WebP, or None when the page cannot be drawn (the document is still readable)."""
    try:
        page = doc[0]
        try:
            width, height = page.get_size()  # points, rotation and crop box applied
            pdfutil.check_page_points(width, height)
            scale = COVER_WIDTH_PX / width
            pdfutil.check_render_pixels(width, height, scale)
            image = page.render(scale=scale, may_draw_forms=False).to_pil().convert("RGB")
        finally:
            page.close()
        buf = io.BytesIO()
        image.save(buf, format="WEBP", quality=80)
        return buf.getvalue()
    except (pdfium.PdfiumError, PdfLimitError, OSError, ValueError):
        return None


def _sample_text(doc: pdfium.PdfDocument, indices: list[int]) -> list[tuple[int, bool]]:
    out: list[tuple[int, bool]] = []
    for index in indices:
        chars, covered = 0, False
        try:
            page = doc[index]
            try:
                textpage = page.get_textpage()
                try:
                    chars = len(textpage.get_text_range().strip())
                finally:
                    textpage.close()
                if chars < MIN_TEXT_CHARS:
                    covered = _image_covers_page(page)
            finally:
                page.close()
        except pdfium.PdfiumError:
            chars, covered = 0, False
        out.append((chars, covered))
    return out


def _image_covers_page(page: pdfium.PdfPage) -> bool:
    width, height = page.get_size()
    area = max(width * height, 1.0)
    for obj in page.get_objects(filter=[pdfium.raw.FPDF_PAGEOBJ_IMAGE], max_depth=2):
        left, bottom, right, top = obj.get_bounds()
        if max(0.0, right - left) * max(0.0, top - bottom) / area >= COVER_PAGE_FRACTION:
            return True
    return False


# --- structure (pikepdf) --------------------------------------------------------------------------------------------


def _has_javascript(pdf: pikepdf.Pdf) -> bool:
    """Information only (never executed): JavaScript in the name tree, an open action, document or page actions, widgets."""
    root = pdf.Root

    def is_js_action(action) -> bool:
        try:
            return isinstance(action, pikepdf.Dictionary) and (
                action.get("/S") == "/JavaScript" or "/JS" in action or is_js_action(action.get("/Next"))
            )
        except (pikepdf.PdfError, RuntimeError):
            return False

    try:
        names = root.get("/Names")
        if names is not None and "/JavaScript" in names:
            return True
        if is_js_action(root.get("/OpenAction")):
            return True
        for container in [root.get("/AA")]:
            if container is not None and any(is_js_action(v) for v in container.values()):
                return True
        inspected = 0
        for page in pdf.pages:
            aa = page.obj.get("/AA")
            if aa is not None and any(is_js_action(v) for v in aa.values()):
                return True
            for annot in page.obj.get("/Annots") or []:
                inspected += 1
                if inspected > 5000:
                    return False
                if is_js_action(annot.get("/A")):
                    return True
                aa = annot.get("/AA")
                if aa is not None and any(is_js_action(v) for v in aa.values()):
                    return True
    except (pikepdf.PdfError, RuntimeError, ValueError, TypeError):
        return False
    return False


def _clean_title(raw) -> str:
    return str(raw).replace("\x00", "").strip()[:OUTLINE_TITLE_MAX]


def _outline(pdf: pikepdf.Pdf, page_count: int) -> list[dict]:
    try:
        page_index = {page.objgen: i + 1 for i, page in enumerate(pdf.pages)}
        named = _named_destinations(pdf)
        budget = [OUTLINE_MAX_NODES]

        def page_of(item) -> int | None:
            dest = item.destination
            if dest is None and item.action is not None and item.action.get("/S") == "/GoTo":
                dest = item.action.get("/D")
            if isinstance(dest, pikepdf.Name | pikepdf.String):
                dest = named.get(str(dest).lstrip("/"))
            if isinstance(dest, pikepdf.Dictionary):
                dest = dest.get("/D")
            if isinstance(dest, pikepdf.Array) and len(dest):
                first = dest[0]
                if isinstance(first, pikepdf.Object) and first.is_indirect:
                    return page_index.get(first.objgen)
                if isinstance(first, int) and 0 <= first < page_count:
                    return first + 1
            return None

        def walk(items, depth: int) -> list[dict]:
            nodes: list[dict] = []
            for item in items:
                if budget[0] <= 0:
                    break
                budget[0] -= 1
                children = walk(item.children, depth + 1) if depth < OUTLINE_MAX_DEPTH else []
                nodes.append({"title": _clean_title(item.title), "page": page_of(item), "children": children})
            return nodes

        with pdf.open_outline() as outline:
            return walk(outline.root, 1)
    except (pikepdf.PdfError, RuntimeError, ValueError, TypeError, AttributeError, RecursionError):
        return []


def _named_destinations(pdf: pikepdf.Pdf) -> dict[str, pikepdf.Object]:
    out: dict[str, pikepdf.Object] = {}
    try:
        legacy = pdf.Root.get("/Dests")
        if legacy is not None:
            for key, value in legacy.items():
                out[str(key).lstrip("/")] = value
        names = pdf.Root.get("/Names")
        if names is not None and "/Dests" in names:
            tree = pikepdf.NameTree(names.Dests)
            for count, (key, value) in enumerate(tree.items()):
                if count >= OUTLINE_MAX_NODES * 4:
                    break
                out[str(key)] = value
    except (pikepdf.PdfError, RuntimeError, ValueError, TypeError, AttributeError):
        pass
    return out
