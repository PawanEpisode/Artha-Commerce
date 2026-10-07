"""
Ink simplification (ERD 3.5), pure. TypeScript twin: `web/src/modules/notes/lib/simplify.ts`, shared fixture
`tests/fixtures/simplify_cases.json`.

Why: a pen sampled at 120 Hz produces thousands of points per word, almost all on straight runs. Ramer-Douglas-Peucker keeps
the points that change the shape by more than `tolerance` (0.0005 of the page, half a pixel at 1000 px) so a drawing stays
well under the 64 KB / 20,000 point limits of Geometry v1 without visible change.

- `simplify_points`: RDP, iterative (no recursion depth problem on 20,000 points), distance to the chord through the
  segment's end points, ties go to the first point. Ends are always kept.
- `group_bursts`: strokes whose start is at most 2 s after the previous stroke ended belong to one annotation (one
  drawing), as the PRD describes; also closes a burst at 50 strokes, the geometry limit.
- `limit_points`: the guard before validation: if a drawing is still over the point limit, double the tolerance until it
  fits (at most 8 times), and as the last resort keep evenly spaced points. Never raises. The result is within the limit as long as
the limit allows two points per stroke (it is 20,000 for at most 50 strokes).
"""

from __future__ import annotations

import math
from typing import Any

from .geometry import MAX_POINTS, MAX_STROKES

DEFAULT_TOLERANCE = 0.0005
BURST_GAP_MS = 2000
_MAX_DOUBLINGS = 8

Point = list[float]
Stroke = dict[str, Any]


def _distance(p: Point, a: Point, b: Point) -> float:
    dx, dy = b[0] - a[0], b[1] - a[1]
    length2 = dx * dx + dy * dy
    if length2 == 0:  # closed loop or a repeated point: distance to the point itself
        return math.sqrt((p[0] - a[0]) ** 2 + (p[1] - a[1]) ** 2)
    return abs(dx * (a[1] - p[1]) - (a[0] - p[0]) * dy) / math.sqrt(length2)


def simplify_points(pts: list[Point], tolerance: float = DEFAULT_TOLERANCE) -> list[Point]:
    """Ramer-Douglas-Peucker. Returns a new list holding a subset of the input points, in order, ends included."""
    n = len(pts)
    if n <= 2:
        return [list(p) for p in pts]
    keep = [False] * n
    keep[0] = keep[n - 1] = True
    stack = [(0, n - 1)]
    while stack:
        lo, hi = stack.pop()
        if hi - lo < 2:
            continue
        far, far_d = -1, 0.0
        for i in range(lo + 1, hi):
            d = _distance(pts[i], pts[lo], pts[hi])
            if d > far_d:
                far, far_d = i, d
        if far_d > tolerance:
            keep[far] = True
            stack.append((lo, far))
            stack.append((far, hi))
    return [list(p) for p, k in zip(pts, keep, strict=True) if k]


def simplify_stroke(stroke: Stroke, tolerance: float = DEFAULT_TOLERANCE) -> Stroke:
    return {**stroke, "pts": simplify_points(stroke["pts"], tolerance)}


def group_bursts(
    strokes: list[Stroke], gap_ms: float = BURST_GAP_MS, max_strokes: int = MAX_STROKES
) -> list[list[Stroke]]:
    """
    Group strokes `{pts, w, t0, t1}` (milliseconds) into drawings. Input is ordered by start time first (stable), then a
    stroke joins the current drawing when it starts within `gap_ms` of the latest end so far and the drawing has room.
    """
    ordered = sorted(strokes, key=lambda s: s["t0"])
    groups: list[list[Stroke]] = []
    latest_end = 0.0
    for s in ordered:
        if groups and s["t0"] - latest_end <= gap_ms and len(groups[-1]) < max_strokes:
            groups[-1].append(s)
            latest_end = max(latest_end, s.get("t1", s["t0"]))
        else:
            groups.append([s])
            latest_end = s.get("t1", s["t0"])
    return groups


def _evenly(pts: list[Point], keep: int) -> list[Point]:
    n = len(pts)
    return [list(pts[i * (n - 1) // (keep - 1)]) for i in range(keep)]  # integer maths: same indices in both languages


def limit_points(
    strokes: list[Stroke], max_points: int = MAX_POINTS, tolerance: float = DEFAULT_TOLERANCE
) -> list[Stroke]:
    """Strokes whose points total at most `max_points`, by simplifying harder, then by thinning evenly."""
    total = sum(len(s["pts"]) for s in strokes)
    if total <= max_points:
        return [{**s, "pts": [list(p) for p in s["pts"]]} for s in strokes]
    tol = tolerance
    for _ in range(_MAX_DOUBLINGS):
        tol *= 2
        out = [simplify_stroke(s, tol) for s in strokes]
        if sum(len(s["pts"]) for s in out) <= max_points:
            return out
    out = []
    for s in strokes:
        pts = s["pts"]
        share = max(2, max_points * len(pts) // total)  # each stroke keeps its proportional share, ends included
        out.append({**s, "pts": _evenly(pts, share) if len(pts) > share else [list(p) for p in pts]})
    return out
