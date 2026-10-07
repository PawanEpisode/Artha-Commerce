"""
`build_flattened_pdf`: burn a student's marks into a copy of their PDF (ERD 6.5 Export job).

The source file is opened read-only and never written. For each page that has marks we append one overlay content stream
(wrapped in its own `q`/`Q` so the original graphics state cannot leak in or out) drawn in the page's *displayed* frame:
a matrix derived from the CropBox origin and the intrinsic /Rotate maps (x, y) with origin bottom-left of the displayed
page to user space, so a mark lands on the same text on rotated and cropped pages. Normalised mark geometry (ERD 3.5:
origin top-left, 0..1) converts to that frame with `y_up = (1 - y) * height`.

Highlights use `/BM /Multiply` so the text stays black; the graphics state also sets `/ca 0.35`, so a viewer that ignores
blend modes shows a translucent colour instead of an opaque block. Text (text boxes, sticky numbers, appendix) goes through
`_fonts` (HarfBuzz shaping, embedded Noto subsets). Appendix pages are laid out with the same engine instead of reportlab
because reportlab cannot shape Devanagari.
"""

from __future__ import annotations

import os
import time
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field

import pikepdf

from . import pdfutil
from ._fonts import FontSet, FontsMissing, default_fonts_dir  # noqa: F401 - re-exported for the glue handler

DEFAULT_TIME_BUDGET_SECONDS = 180.0  # ERD 6.5: three minutes
HIGHLIGHT_ALPHA = 0.35
TINT_ALPHA = 0.35
STICKY_SIZE = 16.0
APPENDIX_PAGE = (595.28, 841.89)  # A4
APPENDIX_MARGIN = 50.0

# Fixed colours for the colour keys, as sRGB 0..1. KEEP IN SYNC with the tokens in `packages/design-system/src/styles.css`
# (`--highlight-*`, `--highlight-*-edge`, `--ink-*`); the final hex values are printed by
# `pnpm --filter @artha/design-system check:contrast`. Highlight fills are drawn with multiply at HIGHLIGHT_ALPHA, so they
# stay pale; underlines use the stronger edge colour so they keep 3:1 against the page.
COLOR_RGB: dict[str, tuple[float, float, float]] = {
    "y": (0.914, 0.788, 0.267),  # #e9c944
    "g": (0.471, 0.886, 0.573),  # #78e292
    "b": (0.573, 0.796, 0.984),  # #92cbfb
    "p": (0.996, 0.667, 0.82),  # #feaad1
    "o": (0.988, 0.694, 0.494),  # #fcb17e
    "i1": (0.435, 0.443, 0.471),  # #6f7178
    "i2": (0.816, 0.173, 0.165),  # #d02c2a
    "i3": (0.196, 0.416, 0.851),  # #326ad9
    "i4": (0.09, 0.518, 0.247),  # #17843f
    "i5": (0.545, 0.267, 0.722),  # #8b44b8
}
EDGE_RGB: dict[str, tuple[float, float, float]] = {
    "y": (0.58, 0.467, 0.102),  # #94771a
    "g": (0.204, 0.561, 0.31),  # #348f4f
    "b": (0.075, 0.502, 0.78),  # #1380c7
    "p": (0.753, 0.275, 0.533),  # #c04688
    "o": (0.71, 0.38, 0.086),  # #b56116
}
HIGHLIGHT_KEYS = ("y", "g", "b", "p", "o")
INK_KEYS = ("i1", "i2", "i3", "i4", "i5")
# Body text of a tinted text box: near black on the (original) page, unlike the mid-tone pen ink-1.
TEXT_RGB = (0.10, 0.10, 0.12)
DRAWN_KINDS = ("highlight", "underline", "area", "ink", "textbox", "sticky")


class ExportTooLarge(Exception):
    """Over 1,000 pages or over the time budget. `suggested_range` is a (first, last) page range that should fit."""

    def __init__(self, message: str, suggested_range: tuple[int, int] | None = None):
        super().__init__(message)
        self.suggested_range = suggested_range


class ExportNotAllowed(Exception):
    """The file's permissions forbid copying or modification (owner-password PDFs); no flattened copy is made."""


@dataclass(frozen=True)
class SkippedMark:
    index: int  # position in the `marks` list
    page: int
    kind: str
    reason: str  # invalid_geometry | unsupported_kind | page_out_of_range | not_rendered


@dataclass(frozen=True)
class ExportResult:
    page_count: int  # pages in the output file, appendix included
    skipped: tuple[SkippedMark, ...] = ()
    appendix_pages: int = 0
    marks_drawn: int = 0


@dataclass
class _PageOverlay:
    ops: list[str] = field(default_factory=list)
    faces: set = field(default_factory=set)  # fonts used on this page
    gstates: set[str] = field(default_factory=set)


def _num(value: float) -> str:
    text = f"{value:.3f}".rstrip("0").rstrip(".")
    return "0" if text in ("", "-0") else text


def _rgb(key: str | None, default: str) -> tuple[float, float, float]:
    return COLOR_RGB.get(key or "", COLOR_RGB[default])


def build_flattened_pdf(
    src_path: str | os.PathLike,
    marks: Sequence[dict],
    out_path: str | os.PathLike,
    *,
    pages: Iterable[int] | None = None,
    include: Iterable[str] | None = None,
    appendix: bool = False,
    fonts_dir: str | os.PathLike | None = None,
    time_budget_seconds: float = DEFAULT_TIME_BUDGET_SECONDS,
    password: str | None = None,
) -> ExportResult:
    """
    Writes `out_path` (never the source). `pages` limits the output to those 1-based pages of the source, in document order;
    `include` limits which mark kinds are drawn (default all). Marks whose `page` refers to the ORIGINAL page numbers.
    Raises `ExportTooLarge`, `ExportNotAllowed`, `FontsMissing`, `PdfOpenError`.
    """
    if os.path.abspath(src_path) == os.path.abspath(out_path):
        raise ValueError("The output must be a different file from the source.")
    started = time.monotonic()
    fonts = FontSet(fonts_dir or default_fonts_dir())
    kinds = frozenset(include) if include is not None else frozenset(DRAWN_KINDS)

    with pdfutil.open_pikepdf(src_path, password=password) as pdf:
        if pdf.is_encrypted and not (pdf.allow.extract and pdf.allow.modify_other):
            raise ExportNotAllowed("The file's permissions do not allow a modified copy.")
        total = len(pdf.pages)
        keep = _selected_pages(pages, total)
        if len(keep) > pdfutil.MAX_PAGES:
            raise ExportTooLarge(
                f"{len(keep)} pages is over the {pdfutil.MAX_PAGES} page limit.",
                (keep[0], keep[pdfutil.MAX_PAGES - 1]),
            )
        originals = {n: pdf.pages[n - 1] for n in keep}
        for n in range(total, 0, -1):
            if n not in originals:
                del pdf.pages[n - 1]

        numbering = _appendix_numbering(marks, kinds, set(keep)) if appendix else {}
        by_page: dict[int, list[tuple[int, dict]]] = {}
        skipped: list[SkippedMark] = []
        for index, mark in enumerate(marks):
            number = mark.get("page")
            kind = mark.get("kind")
            if kind not in kinds:
                continue
            if not isinstance(number, int) or not 1 <= number <= total:
                skipped.append(
                    SkippedMark(index, number if isinstance(number, int) else 0, str(kind), "page_out_of_range")
                )
                continue
            if number not in originals:
                continue
            if kind not in DRAWN_KINDS:
                skipped.append(SkippedMark(index, number, str(kind), "not_rendered"))
                continue
            by_page.setdefault(number, []).append((index, mark))

        styles = _GraphicsStates(pdf)
        drawn = 0
        done = 0
        for number in keep:
            if time.monotonic() - started > time_budget_seconds:
                raise ExportTooLarge("The export took longer than the time budget.", (keep[0], keep[max(done - 1, 0)]))
            done += 1
            entries = by_page.get(number)
            if not entries:
                continue
            page = originals[number]
            w, h, rotation = pdfutil.displayed_size(page.obj)
            overlay = _PageOverlay()
            for index, mark in entries:
                try:
                    ok = _draw_mark(overlay, fonts, mark, w, h, numbering.get(index))
                except (KeyError, TypeError, ValueError, IndexError):
                    ok = False
                if ok:
                    drawn += 1
                else:
                    skipped.append(SkippedMark(index, number, str(mark.get("kind")), "invalid_geometry"))
            if overlay.ops:
                _attach_overlay(pdf, page, overlay, fonts, styles, rotation)

        appendix_pages = 0
        if appendix and numbering:
            appendix_pages = _build_appendix(pdf, fonts, marks, numbering, started, time_budget_seconds)

        fonts.embed_all(pdf)
        pdf.save(os.fspath(out_path), compress_streams=True, object_stream_mode=pikepdf.ObjectStreamMode.generate)
        return ExportResult(len(pdf.pages), tuple(sorted(skipped, key=lambda m: m.index)), appendix_pages, drawn)


def _selected_pages(pages: Iterable[int] | None, total: int) -> list[int]:
    if pages is None:
        return list(range(1, total + 1))
    chosen = sorted({int(p) for p in pages})
    if not chosen or chosen[0] < 1 or chosen[-1] > total:
        raise ValueError("`pages` must be 1-based page numbers inside the document.")
    return chosen


# --- graphics states and overlay attachment -------------------------------------------------------------------------


class _GraphicsStates:
    """The shared ExtGState objects, created once per output file."""

    def __init__(self, pdf: pikepdf.Pdf):
        def gs(**kw) -> pikepdf.Object:
            return pdf.make_indirect(pikepdf.Dictionary(Type=pikepdf.Name.ExtGState, **kw))

        self.objects = {
            "ArthaHl": gs(BM=pikepdf.Name.Multiply, ca=HIGHLIGHT_ALPHA, CA=HIGHLIGHT_ALPHA),
            "ArthaN": gs(BM=pikepdf.Name.Normal, ca=1, CA=1),
            "ArthaTint": gs(BM=pikepdf.Name.Normal, ca=TINT_ALPHA, CA=TINT_ALPHA),
        }


def _display_matrix(box: tuple[float, float, float, float], rotation: int) -> tuple[float, ...]:
    """Maps y-up coordinates of the displayed page (origin bottom-left) to user space; see the module docstring."""
    x0, y0, x1, y1 = box
    return {
        0: (1, 0, 0, 1, x0, y0),
        90: (0, 1, -1, 0, x1, y0),
        180: (-1, 0, 0, -1, x1, y1),
        270: (0, -1, 1, 0, x0, y1),
    }[rotation]


def _attach_overlay(pdf, page, overlay: _PageOverlay, fonts: FontSet, styles: _GraphicsStates, rotation: int) -> None:
    box = pdfutil.page_box(page.obj)
    matrix = " ".join(_num(v) for v in _display_matrix(box, rotation))
    fonts.prepare(pdf)
    resources = pikepdf.Dictionary()
    existing = page.obj.get("/Resources") or pdfutil.inherited(page.obj, "/Resources")
    if existing is not None:
        for key, value in existing.items():
            resources[key] = value
    ext = pikepdf.Dictionary()
    old_ext = resources.get("/ExtGState")
    if old_ext is not None:
        for key, value in old_ext.items():
            ext[key] = value
    for name in overlay.gstates:
        ext["/" + name] = styles.objects[name]
    resources["/ExtGState"] = ext
    if overlay.faces:
        font_dict = pikepdf.Dictionary()
        old_fonts = resources.get("/Font")
        if old_fonts is not None:
            for key, value in old_fonts.items():
                font_dict[key] = value
        for face in overlay.faces:
            font_dict["/" + face.resource_name] = face.font_object
        resources["/Font"] = font_dict
    page.obj.Resources = resources
    body = f"Q\nq\n{matrix} cm\n" + "\n".join(overlay.ops) + "\nQ\n"
    page.contents_add(pdf.make_stream(b"q\n"), prepend=True)
    page.contents_add(pdf.make_stream(body.encode("ascii")))


# --- drawing marks (display frame, y up) ----------------------------------------------------------------------------


def _unit(value) -> float:
    number = float(value)
    if not -0.01 <= number <= 1.01:
        raise ValueError("outside the page")
    return number


def _rect(geom: Sequence, w: float, h: float) -> tuple[float, float, float, float]:
    x, y, rw, rh = (_unit(v) for v in geom)
    if rw <= 0 or rh <= 0:
        raise ValueError("empty rectangle")
    return x * w, (1 - (y + rh)) * h, rw * w, rh * h  # left, bottom, width, height in points


def _draw_mark(overlay: _PageOverlay, fonts: FontSet, mark: dict, w: float, h: float, number: int | None) -> bool:
    kind, geom = mark["kind"], mark["geometry"]
    ops = overlay.ops
    if kind in ("highlight", "area"):
        rects = geom["quads"] if kind == "highlight" else [geom["rect"]]
        if not 1 <= len(rects) <= 200:
            return False
        r, g, b = _rgb(mark.get("color"), "y")
        boxes = [_rect(q, w, h) for q in rects]
        overlay.gstates.add("ArthaHl")
        body = "\n".join(f"{_num(left)} {_num(bt)} {_num(bw)} {_num(bh)} re" for left, bt, bw, bh in boxes)
        ops.append(f"q /ArthaHl gs {_num(r)} {_num(g)} {_num(b)} rg\n{body}\nf Q")
        return True
    if kind == "underline":
        rects = geom["quads"]
        if not 1 <= len(rects) <= 200:
            return False
        r, g, b = EDGE_RGB.get(mark.get("color") or "") or _rgb(mark.get("color"), "y")
        overlay.gstates.add("ArthaN")
        lines = []
        for left, bt, bw, bh in (_rect(q, w, h) for q in rects):
            y = bt + max(0.4, bh * 0.08)
            lines.append(f"{_num(left)} {_num(y)} m {_num(left + bw)} {_num(y)} l S")
        width = _num(max(0.6, min(1.6, 0.07 * _rect(rects[0], w, h)[3])))
        ops.append(f"q /ArthaN gs {_num(r)} {_num(g)} {_num(b)} RG {width} w 1 J\n" + "\n".join(lines) + "\nQ")
        return True
    if kind == "ink":
        strokes = geom["strokes"]
        if not 1 <= len(strokes) <= 50:
            return False
        r, g, b = _rgb(mark.get("color"), "i1")
        overlay.gstates.add("ArthaN")
        paths = []
        for stroke in strokes:
            pts = [(_unit(px) * w, (1 - _unit(py)) * h) for px, py in stroke["pts"]]
            if not pts:
                continue
            width = min(max(float(stroke.get("w", 0.0035)), 0.001), 0.02) * w
            if len(pts) == 1:
                pts.append((pts[0][0] + 0.01, pts[0][1]))
            path = f"{_num(width)} w {_num(pts[0][0])} {_num(pts[0][1])} m " + " ".join(
                f"{_num(x)} {_num(y)} l" for x, y in pts[1:]
            )
            paths.append(path + " S")
        if not paths:
            return False
        ops.append(f"q /ArthaN gs {_num(r)} {_num(g)} {_num(b)} RG 1 J 1 j\n" + "\n".join(paths) + "\nQ")
        return True
    if kind == "textbox":
        return _draw_textbox(overlay, fonts, mark, geom, w, h)
    if kind == "sticky":
        px, py = (_unit(v) for v in geom["pt"])
        return _draw_sticky(overlay, fonts, mark, px * w, (1 - py) * h, number)
    return False


def _draw_textbox(overlay: _PageOverlay, fonts: FontSet, mark: dict, geom: dict, w: float, h: float) -> bool:
    text = str(mark.get("comment") or "").strip()
    if not text:
        return False
    left, bottom, bw, bh = _rect(geom["rect"], w, h)
    size = min(max(float(geom.get("fs", 0.018)), 0.008), 0.06) * h
    pad = size * 0.3
    lines = fonts.wrap(text, size, max(bw - 2 * pad, size))
    leading = size * 1.25
    needed = len(lines) * leading + 2 * pad
    height = max(bh, needed)  # grow downward rather than hide the student's words
    top = bottom + bh
    key = mark.get("color")
    tinted = key in HIGHLIGHT_KEYS
    text_color = TEXT_RGB if tinted or key not in INK_KEYS else COLOR_RGB[key]
    ops = overlay.ops
    if tinted:
        r, g, b = COLOR_RGB[key]
        overlay.gstates.add("ArthaTint")
        ops.append(
            f"q /ArthaTint gs {_num(r)} {_num(g)} {_num(b)} rg {_num(left)} {_num(top - height)} {_num(bw)} {_num(height)} re f Q"
        )
    r, g, b = text_color
    overlay.gstates.add("ArthaN")
    body = []
    baseline = top - pad - size * 0.95
    for line in lines:
        glyphs, _ = fonts.shape_text(line, size)
        overlay.faces.update(g_.face for g_ in glyphs)
        body.append(fonts.emit(glyphs, size, left + pad, baseline, line))
        baseline -= leading
    ops.append(f"q /ArthaN gs {_num(r)} {_num(g)} {_num(b)} rg\n" + "\n".join(x for x in body if x) + "\nQ")
    return True


def _draw_sticky(overlay: _PageOverlay, fonts: FontSet, mark: dict, x: float, y: float, number: int | None) -> bool:
    """A note icon with its top-left corner at the anchor point; the appendix number (if any) is drawn inside."""
    s = STICKY_SIZE
    r, g, b = _rgb(mark.get("color"), "y")
    if mark.get("color") in INK_KEYS:
        r, g, b = COLOR_RGB["y"]
    overlay.gstates.add("ArthaN")
    fold = s * 0.28
    left, bottom = x, y - s
    ops = [
        "q /ArthaN gs",
        f"{_num(r)} {_num(g)} {_num(b)} rg 0.2 0.2 0.2 RG 0.7 w",
        f"{_num(left)} {_num(bottom)} m {_num(left + s)} {_num(bottom)} l {_num(left + s)} {_num(bottom + s - fold)} l "
        f"{_num(left + s - fold)} {_num(bottom + s)} l {_num(left)} {_num(bottom + s)} l h B",
        f"{_num(left + s - fold)} {_num(bottom + s)} m {_num(left + s - fold)} {_num(bottom + s - fold)} l "
        f"{_num(left + s)} {_num(bottom + s - fold)} l S",
    ]
    if number is not None:
        size = s * 0.5
        text = str(number)
        glyphs, width = fonts.shape_text(text, size, bold=True)
        overlay.faces.update(g_.face for g_ in glyphs)
        ops.append("0.1 0.1 0.12 rg")
        ops.append(fonts.emit(glyphs, size, left + (s - width) / 2, bottom + s * 0.28))
    ops.append("Q")
    overlay.ops.append("\n".join(ops))
    return True


# --- appendix -------------------------------------------------------------------------------------------------------


def _appendix_numbering(marks: Sequence[dict], kinds: frozenset[str], pages: set[int]) -> dict[int, int]:
    """Numbers the marks listed in the appendix (those with a comment) in page order; sticky icons show the number."""
    listed = [
        (mark["page"], index)
        for index, mark in enumerate(marks)
        if mark.get("kind") in kinds
        and mark.get("kind") in DRAWN_KINDS
        and mark.get("kind") != "textbox"
        and isinstance(mark.get("page"), int)
        and mark["page"] in pages
        and str(mark.get("comment") or "").strip()
    ]
    return {index: n for n, (_, index) in enumerate(sorted(listed), start=1)}


def _build_appendix(pdf, fonts: FontSet, marks, numbering: dict[int, int], started: float, budget: float) -> int:
    width, height = APPENDIX_PAGE
    margin = APPENDIX_MARGIN
    column = width - 2 * margin
    layouts: list[list[str]] = []  # operators per appendix page
    page_faces: list[set] = []
    state = {"ops": [], "faces": set(), "y": height - margin}

    def new_page() -> None:
        if state["ops"]:
            layouts.append(state["ops"])
            page_faces.append(state["faces"])
        state.update(ops=[], faces=set(), y=height - margin)

    def write(text: str, size: float, *, bold=False, rgb=(0.1, 0.1, 0.12), indent=0.0, gap_after=0.0) -> None:
        for line in fonts.wrap(text, size, column - indent, bold):
            leading = size * 1.3
            if state["y"] - leading < margin:
                new_page()
            state["y"] -= leading
            glyphs, _ = fonts.shape_text(line, size, bold)
            state["faces"].update(g.face for g in glyphs)
            ops = fonts.emit(glyphs, size, margin + indent, state["y"], line)
            if ops:
                state["ops"].append(f"{_num(rgb[0])} {_num(rgb[1])} {_num(rgb[2])} rg\n{ops}")
        state["y"] -= gap_after

    if time.monotonic() - started > budget:
        raise ExportTooLarge("The export took longer than the time budget.")
    write("Notes and highlights", 16, bold=True, gap_after=10)
    for index, number in sorted(numbering.items(), key=lambda kv: kv[1]):
        mark = marks[index]
        label = f"{number}.  Page {mark['page']}  ·  {str(mark['kind']).capitalize()}"
        write(label, 9.5, bold=True, rgb=(0.3, 0.3, 0.35), gap_after=1)
        quote = str(mark.get("quote_exact") or "").strip()
        if quote:
            write(
                "“" + quote[:400] + ("…" if len(quote) > 400 else "") + "”",
                9.5,
                rgb=(0.35, 0.35, 0.4),
                indent=10,
                gap_after=1,
            )
        write(str(mark["comment"]).strip()[:4000], 10.5, indent=10, gap_after=9)
    new_page()

    fonts.prepare(pdf)
    for ops, faces in zip(layouts, page_faces, strict=True):
        pdf.add_blank_page(page_size=(width, height))
        page = pdf.pages[-1]
        page.obj.Resources = pikepdf.Dictionary(
            Font=pikepdf.Dictionary({"/" + f.resource_name: f.font_object for f in faces})
        )
        page.obj.Contents = pdf.make_stream("\n".join(ops).encode("ascii"))
    return len(layouts)
