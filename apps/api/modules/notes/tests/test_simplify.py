"""Ink simplification, shared with `simplify.test.ts` through `simplify_cases.json`."""

import json
import math
import random
from pathlib import Path

import pytest

from modules.notes.domain import geometry, simplify

FIXTURES = json.loads((Path(__file__).parent / "fixtures" / "simplify_cases.json").read_text())


@pytest.mark.parametrize("case", FIXTURES["rdp"], ids=lambda c: c["name"])
def test_rdp(case):
    tolerance = case.get("tolerance", simplify.DEFAULT_TOLERANCE)
    assert simplify.simplify_points(case["pts"], tolerance) == case["expected"]


@pytest.mark.parametrize("case", FIXTURES["bursts"], ids=lambda c: c["name"])
def test_bursts(case):
    strokes = [{**s, "pts": [[0.1, 0.1]], "w": 0.0035} for s in case["strokes"]]
    kwargs = {k: case[k] for k in ("gap_ms", "max_strokes") if k in case}
    assert [[s["id"] for s in g] for g in simplify.group_bursts(strokes, **kwargs)] == case["expected"]


@pytest.mark.parametrize("case", FIXTURES["limit"], ids=lambda c: c["name"])
def test_limit_points(case):
    assert simplify.limit_points(case["strokes"], case["max_points"]) == case["expected"]


def test_simplified_points_stay_within_the_tolerance_of_the_original():
    rng = random.Random(7)
    pts = [[i / 400, 0.5 + 0.2 * math.sin(i / 25) + rng.uniform(-0.0002, 0.0002)] for i in range(400)]
    out = simplify.simplify_points(pts)
    assert len(out) < 120 and out[0] == pts[0] and out[-1] == pts[-1]
    # RDP guarantee: every original point is within the tolerance of the chord between the kept points that bracket it
    kept_at = [i for i, p in enumerate(pts) if p in out]
    for lo, hi in zip(kept_at, kept_at[1:], strict=False):
        for i in range(lo + 1, hi):
            assert simplify._distance(pts[i], pts[lo], pts[hi]) <= simplify.DEFAULT_TOLERANCE


def test_a_dense_drawing_fits_geometry_v1_after_the_guard():
    stroke = {"pts": [[(i % 997) / 997, (i * 31 % 991) / 991] for i in range(30_000)], "w": 0.0035}
    out = simplify.limit_points([stroke])
    assert sum(len(s["pts"]) for s in out) <= geometry.MAX_POINTS


def test_the_input_is_never_mutated():
    stroke = {"pts": [[0.1, 0.1], [0.2, 0.2], [0.3, 0.1]], "w": 0.0035, "t0": 1}
    before = json.dumps(stroke)
    simplify.simplify_stroke(stroke)
    simplify.limit_points([stroke], 2)
    assert json.dumps(stroke) == before
