"""
Coordinate maths for marks on a PDF page (ERD 3.5, the "worked example"), pure. The TypeScript twin is
`web/src/modules/notes/lib/coords.ts`; both read `tests/fixtures/coords_cases.json`.

Frames, from the stored one outwards:
- Stored: the page as displayed with its intrinsic `/Rotate` applied, origin top-left, fractions of width and height.
- Viewed: the stored frame turned by the student's rotation (0, 90, 180 or 270 degrees clockwise). Pure transform, nothing
  is stored.
- PDF user space: what the export writes into: the unrotated page box, origin bottom-left, in points.
`rect_to_user_space` is the one the export needs: a mark stored against a page whose `/Rotate` is 90 must land on the
right words in the raw PDF, where the page is still unrotated.
"""

from __future__ import annotations

import math

from .geometry import round5

Rect = list[float]


def normalise_rotation(degrees: float) -> int:
    """0, 90, 180 or 270 for any multiple of 90 (negatives and 360+ wrap); anything else is a programming error."""
    if degrees != int(degrees) or int(degrees) % 90 != 0:
        raise ValueError(f"rotation must be a multiple of 90, got {degrees}")
    return int(degrees) % 360


def view_size(page_w: float, page_h: float, rotation: float) -> tuple[float, float]:
    """Width and height of the page as viewed: swapped at 90 and 270."""
    return (page_h, page_w) if normalise_rotation(rotation) in (90, 270) else (page_w, page_h)


def normalise_rect(x: float, y: float, w: float, h: float, page_w: float, page_h: float) -> Rect:
    """A rectangle in points (top-left origin, page as displayed) to the stored frame. 119, 168.4, 238, 13.4 on 595 x 842 is
    [0.2, 0.2, 0.4, 0.01591]."""
    return [round5(x / page_w), round5(y / page_h), round5(w / page_w), round5(h / page_h)]


def denormalise_rect(rect: Rect, page_w: float, page_h: float) -> Rect:
    return [rect[0] * page_w, rect[1] * page_h, rect[2] * page_w, rect[3] * page_h]


def rotate_point(pt: list[float], rotation: float) -> list[float]:
    """Stored point to the viewed frame. A clockwise quarter turn sends the top-left corner to the top-right: (x, y) -> (1 - y, x)."""
    x, y = pt
    r = normalise_rotation(rotation)
    if r == 90:
        return [round5(1 - y), round5(x)]
    if r == 180:
        return [round5(1 - x), round5(1 - y)]
    if r == 270:
        return [round5(y), round5(1 - x)]
    return [round5(x), round5(y)]


def rotate_rect(rect: Rect, rotation: float) -> Rect:
    """Stored rectangle to the viewed frame (width and height swap at 90 and 270). Rounded to five decimals like stored values."""
    x, y, w, h = rect
    r = normalise_rotation(rotation)
    if r == 90:
        return [round5(1 - y - h), round5(x), round5(h), round5(w)]
    if r == 180:
        return [round5(1 - x - w), round5(1 - y - h), round5(w), round5(h)]
    if r == 270:
        return [round5(y), round5(1 - x - w), round5(h), round5(w)]
    return [round5(v) for v in rect]


def unrotate_rect(rect: Rect, rotation: float) -> Rect:
    """Viewed rectangle back to the stored frame: the inverse of `rotate_rect`."""
    return rotate_rect(rect, -normalise_rotation(rotation))


def unrotate_point(pt: list[float], rotation: float) -> list[float]:
    return rotate_point(pt, -normalise_rotation(rotation))


def _round_pt(v: float) -> float:
    return math.floor(v * 1000 + 0.5) / 1000  # points to a thousandth: far below anything a PDF viewer draws


def rect_to_user_space(rect: Rect, intrinsic_rotate: float, box_w: float, box_h: float) -> Rect:
    """
    A stored rectangle as `[x, y, w, h]` in PDF user space (points, origin bottom-left, `(x, y)` is the lower-left corner).
    `box_w` and `box_h` are the UNROTATED page box. Undo the page's `/Rotate` first, then scale and flip y. A point mark is
    a rectangle with zero width and height.
    """
    bx, by, bw, bh = unrotate_rect(rect, intrinsic_rotate)
    top = by * box_h
    return [_round_pt(bx * box_w), _round_pt(box_h - (top + bh * box_h)), _round_pt(bw * box_w), _round_pt(bh * box_h)]
