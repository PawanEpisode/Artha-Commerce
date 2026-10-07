"""
Geometry v1 (ERD 3.5): validate and normalise the shape of a mark on a PDF page. Pure, no Django.

Why a Python and a TypeScript copy: the client validates before it queues a write (offline), the server validates again
because it never trusts a client. Both read the same golden fixtures (`tests/fixtures/geometry_cases.json`), so a rule
cannot change in one place only. Keep `web/src/modules/notes/lib/geometry.ts` in step.

Frame: the page as displayed with its intrinsic rotation applied, origin top-left, x/y/w/h as fractions of the page's
width and height (ERD decision 3). Everything is rounded to five decimals with `round5` (half up on the decimal value,
not Python's banker's `round`, so both languages agree to the last digit).

`validate_geometry(kind, geometry)` returns `{"geometry": normalised | None, "errors": [{"code", "message"}]}`. Errors have
a stable `code` (listed in `ERROR_CODES`), each reported at most once, so the UI can map a code to a translated message.
Unknown keys are dropped. The ink `bbox` is always recomputed from the points: a client bbox is never trusted.
"""

from __future__ import annotations

import math
from typing import Any

KINDS = ("highlight", "underline", "area", "ink", "textbox", "sticky", "bookmark")
ERROR_CODES = (
    "bad_kind",
    "bad_shape",
    "out_of_range",
    "too_many_quads",
    "quad_too_small",
    "rect_too_small",
    "too_many_strokes",
    "too_many_points",
    "too_large",
    "bad_width",
    "bad_font_size",
)

MAX_QUADS = 200
MIN_QUAD_W, MIN_QUAD_H = 0.002, 0.004
MIN_RECT_W, MIN_RECT_H = 0.004, 0.004  # area and text box: smaller than a finger tap is a mistake, not a mark
MAX_STROKES, MAX_POINTS = 50, 20_000
MIN_STROKE_W, MAX_STROKE_W = 0.001, 0.02
MIN_FONT, MAX_FONT = 0.008, 0.06
MAX_BYTES = 64 * 1024  # the database checks `length(geometry::text)`; `serialised_size` mimics that text
MERGE_GAP = 0.005  # about one word space on an A4 page
MERGE_LINE_OVERLAP = 0.5  # two quads are "the same line" when they overlap vertically by half the smaller height
_EPS = 1e-9  # float noise from the client's own multiplication must not reject a rectangle that ends exactly at 1

Rect = list[float]


def round5(x: float) -> float:
    """Five decimals, half up on the decimal value. Python's `round` is banker's and differs from JS `Math.round`."""
    return math.floor(x * 100_000 + 0.5) / 100_000


def _is_num(v: Any) -> bool:
    return isinstance(v, int | float) and not isinstance(v, bool) and math.isfinite(v)


def _is_seq(v: Any, n: int | None = None) -> bool:
    return isinstance(v, list | tuple) and (n is None or len(v) == n)


class _Errors:
    def __init__(self) -> None:
        self.items: list[dict[str, str]] = []

    def add(self, code: str, message: str) -> None:
        if all(e["code"] != code for e in self.items):
            self.items.append({"code": code, "message": message})


def _unit(v: Any) -> bool:
    return _is_num(v) and -_EPS <= v <= 1 + _EPS


def _rect(value: Any, errs: _Errors, min_w: float, min_h: float, small: str) -> Rect | None:
    if not (_is_seq(value, 4) and all(_is_num(v) for v in value)):
        errs.add("bad_shape", "A rectangle is [x, y, w, h] with four numbers.")
        return None
    x, y, w, h = value
    if not all(_unit(v) for v in value) or x + w > 1 + _EPS or y + h > 1 + _EPS:
        errs.add("out_of_range", "The rectangle must lie inside the page (0 to 1).")
        return None
    if w < min_w or h < min_h:
        errs.add(small, "The rectangle is too small.")
        return None
    rx, ry = round5(x), round5(y)
    return [rx, ry, min(round5(w), round5(1 - rx)), min(round5(h), round5(1 - ry))]


def _mergeable(a: Rect, b: Rect) -> bool:
    overlap = min(a[1] + a[3], b[1] + b[3]) - max(a[1], b[1])
    gap = max(a[0], b[0]) - min(a[0] + a[2], b[0] + b[2])
    return overlap >= MERGE_LINE_OVERLAP * min(a[3], b[3]) and gap <= MERGE_GAP


def _union(a: Rect, b: Rect) -> Rect:
    x, y = min(a[0], b[0]), min(a[1], b[1])
    return [x, y, max(a[0] + a[2], b[0] + b[2]) - x, max(a[1] + a[3], b[1] + b[3]) - y]


def merge_adjacent_quads(quads: list[Rect]) -> list[Rect]:
    """
    Merge line rectangles that sit on the same line and touch (a gap of at most one word space). A selection that pdf.js
    returns word by word becomes one rectangle per line. Merged rectangles keep the position of the first one (reading
    order is preserved); the result is rounded with `round5`. Quadratic, which is fine for at most 200 quads.
    """
    out = [list(q) for q in quads]
    merged = True
    while merged:
        merged = False
        for i in range(len(out)):
            for j in range(i + 1, len(out)):
                if _mergeable(out[i], out[j]):
                    out[i] = _union(out[i], out[j])
                    del out[j]
                    merged = True
                    break
            if merged:
                break
    return [[round5(v) for v in q] for q in out]


def _quads(g: dict, errs: _Errors) -> dict | None:
    quads = g.get("quads")
    if not _is_seq(quads) or len(quads) == 0:
        errs.add("bad_shape", "`quads` must be a non-empty list.")
        return None
    if len(quads) > MAX_QUADS:
        errs.add("too_many_quads", f"At most {MAX_QUADS} rectangles.")
        return None
    rects = [_rect(q, errs, MIN_QUAD_W, MIN_QUAD_H, "quad_too_small") for q in quads]
    if any(r is None for r in rects):
        return None
    return {"quads": merge_adjacent_quads(rects)}  # type: ignore[arg-type]


def _ink(g: dict, errs: _Errors) -> dict | None:
    strokes = g.get("strokes")
    if not _is_seq(strokes) or len(strokes) == 0:
        errs.add("bad_shape", "`strokes` must be a non-empty list.")
        return None
    if len(strokes) > MAX_STROKES:
        errs.add("too_many_strokes", f"At most {MAX_STROKES} strokes.")
        return None
    if not all(isinstance(s, dict) and _is_seq(s.get("pts")) and len(s["pts"]) > 0 for s in strokes):
        errs.add("bad_shape", "A stroke is {pts: [[x, y], ...], w}.")
        return None
    if sum(len(s["pts"]) for s in strokes) > MAX_POINTS:
        errs.add("too_many_points", f"At most {MAX_POINTS} points.")
        return None
    out = []
    for s in strokes:
        if not _is_num(s.get("w")) or not MIN_STROKE_W <= s["w"] <= MAX_STROKE_W:
            errs.add("bad_width", f"Stroke width is {MIN_STROKE_W} to {MAX_STROKE_W}.")
            return None
        if not all(_is_seq(p, 2) and all(_is_num(v) for v in p) for p in s["pts"]):
            errs.add("bad_shape", "A point is [x, y].")
            return None
        if not all(_unit(v) for p in s["pts"] for v in p):
            errs.add("out_of_range", "Points must lie inside the page (0 to 1).")
            return None
        out.append({"pts": [[round5(p[0]), round5(p[1])] for p in s["pts"]], "w": round5(s["w"])})
    result = {"strokes": out, "bbox": ink_bbox(out)}
    if serialised_size(result) > MAX_BYTES:
        errs.add("too_large", "The drawing is too large; split it.")
        return None
    return result


def ink_bbox(strokes: list[dict]) -> Rect:
    """Box around all points, grown by half the widest stroke (so the line's thickness is inside) and clamped to the page."""
    xs = [p[0] for s in strokes for p in s["pts"]]
    ys = [p[1] for s in strokes for p in s["pts"]]
    pad = max(s["w"] for s in strokes) / 2
    x0, y0 = max(0.0, min(xs) - pad), max(0.0, min(ys) - pad)
    x1, y1 = min(1.0, max(xs) + pad), min(1.0, max(ys) + pad)
    return [round5(x0), round5(y0), round5(x1 - x0), round5(y1 - y0)]


def _textbox(g: dict, errs: _Errors) -> dict | None:
    rect = _rect(g.get("rect"), errs, MIN_RECT_W, MIN_RECT_H, "rect_too_small")
    fs = g.get("fs")
    if not _is_num(fs) or not MIN_FONT <= fs <= MAX_FONT:
        errs.add("bad_font_size", f"Font size is {MIN_FONT} to {MAX_FONT} of the page height.")
        return None
    return None if rect is None else {"rect": rect, "fs": round5(fs)}


def _area(g: dict, errs: _Errors) -> dict | None:
    rect = _rect(g.get("rect"), errs, MIN_RECT_W, MIN_RECT_H, "rect_too_small")
    return None if rect is None else {"rect": rect}


def _sticky(g: dict, errs: _Errors) -> dict | None:
    pt = g.get("pt")
    if not (_is_seq(pt, 2) and all(_is_num(v) for v in pt)):
        errs.add("bad_shape", "`pt` is [x, y].")
        return None
    if not all(_unit(v) for v in pt):
        errs.add("out_of_range", "The point must lie inside the page (0 to 1).")
        return None
    return {"pt": [round5(pt[0]), round5(pt[1])]}


def _bookmark(g: dict, errs: _Errors) -> dict | None:
    if not _is_num(g.get("y")):
        errs.add("bad_shape", "`y` is a number.")
        return None
    if not _unit(g["y"]):
        errs.add("out_of_range", "`y` must be between 0 and 1.")
        return None
    return {"y": round5(g["y"])}


_VALIDATORS = {
    "highlight": _quads,
    "underline": _quads,
    "ink": _ink,
    "textbox": _textbox,
    "area": _area,
    "sticky": _sticky,
    "bookmark": _bookmark,
}


def validate_geometry(kind: str, geometry: Any) -> dict[str, Any]:
    """Validate and normalise `geometry` for `kind`. `geometry` is None whenever `errors` is not empty."""
    errs = _Errors()
    validator = _VALIDATORS.get(kind) if isinstance(kind, str) else None
    if validator is None:
        errs.add("bad_kind", "Unknown mark kind.")
    elif not isinstance(geometry, dict):
        errs.add("bad_shape", "Geometry must be an object.")
    else:
        normalised = validator(geometry, errs)
        if normalised is not None and not errs.items:
            return {"geometry": normalised, "errors": []}
    return {"geometry": None, "errors": errs.items}


def _number_text(n: float) -> str:
    return f"{n:.5f}".rstrip("0").rstrip(".") or "0"


def serialised_size(value: Any) -> int:
    """
    Length of the value as Postgres prints jsonb (`", "` and `": "` separators, numbers without trailing zeros), which is
    what the database check on `length(geometry::text)` measures. Computed by hand, not with a JSON library, because
    Python and JS format floats differently and the two copies must give the same size.
    """
    if isinstance(value, dict):
        parts = [len(k) + 2 + 2 + serialised_size(v) for k, v in value.items()]
        return 2 + sum(parts) + 2 * max(len(parts) - 1, 0)
    if isinstance(value, list | tuple):
        parts = [serialised_size(v) for v in value]
        return 2 + sum(parts) + 2 * max(len(parts) - 1, 0)
    if isinstance(value, str):
        return len(value) + 2
    return len(_number_text(value))


def geometry_bbox(kind: str, geometry: dict) -> Rect:
    """Bounding box `[x, y, w, h]` of a normalised geometry: lists, thumbnails and the export use it to place a mark."""
    if kind in ("highlight", "underline"):
        box = geometry["quads"][0]
        for q in geometry["quads"][1:]:
            box = _union(box, q)
        return [round5(v) for v in box]
    if kind == "ink":
        return list(geometry["bbox"])
    if kind in ("area", "textbox"):
        return list(geometry["rect"])
    if kind == "sticky":
        return [geometry["pt"][0], geometry["pt"][1], 0.0, 0.0]
    return [0.0, geometry["y"], 1.0, 0.0]  # bookmark: a horizontal line across the page
