"""Geometry v1: the golden fixtures are shared with `geometry.test.ts`, so both languages enforce the same rules."""

import json
from pathlib import Path

import pytest

from modules.notes.domain import geometry as g

FIXTURES = json.loads((Path(__file__).parent / "fixtures" / "geometry_cases.json").read_text())


def _ink_from(spec: dict) -> dict:
    """Deterministic big drawings, generated the same way in the TS test (integer maths, then one division)."""
    return {
        "strokes": [
            {
                "pts": [
                    [
                        round(((i * 7919 + s * 104729) % 99991) / 99991, 5),
                        round(((i * 6271 + s * 7) % 99989) / 99989, 5),
                    ]
                    for i in range(spec["points"])
                ],
                "w": spec.get("w", 0.0035),
            }
            for s in range(spec["strokes"])
        ]
    }


@pytest.mark.parametrize("case", FIXTURES["cases"], ids=lambda c: c["name"])
def test_validate_matches_the_golden_cases(case):
    geometry = _ink_from(case["gen"]) if "gen" in case else case["geometry"]
    result = g.validate_geometry(case["kind"], geometry)
    assert [e["code"] for e in result["errors"]] == case["errors"]
    assert all(e["message"] for e in result["errors"])
    if "gen" in case and case["expected"]:
        got = result["geometry"]
        assert {"size": g.serialised_size(got), "strokes": len(got["strokes"]), "bbox": got["bbox"]} == case["expected"]
    else:
        assert result["geometry"] == case["expected"]


@pytest.mark.parametrize("case", FIXTURES["merge"], ids=lambda c: c["name"])
def test_merge_adjacent_quads(case):
    assert g.merge_adjacent_quads(case["quads"]) == case["expected"]


@pytest.mark.parametrize("case", FIXTURES["bbox"], ids=lambda c: c["name"])
def test_bbox(case):
    assert g.geometry_bbox(case["kind"], case["geometry"]) == case["expected"]


@pytest.mark.parametrize("case", FIXTURES["size"], ids=lambda c: c["name"])
def test_serialised_size(case):
    assert g.serialised_size(case["value"]) == case["expected"]


def test_error_codes_are_the_documented_ones():
    seen = {code for c in FIXTURES["cases"] for code in c["errors"]}
    assert seen <= set(g.ERROR_CODES)
    assert {"bad_kind", "bad_shape", "out_of_range", "too_many_quads", "quad_too_small", "too_many_strokes"} <= seen
    assert {"too_many_points", "too_large", "bad_width", "bad_font_size", "rect_too_small"} <= seen


def test_round5_is_half_up_on_the_decimal_value():
    assert g.round5(0.123455) == 0.12346  # Python's round() would give 0.12345 or 0.12346 depending on binary noise
    assert g.round5(0.2) == 0.2
    assert g.round5(0.015914) == 0.01591


def test_normalising_twice_changes_nothing():
    for case in FIXTURES["cases"]:
        if case["expected"] and "gen" not in case:
            again = g.validate_geometry(case["kind"], case["expected"])
            assert again == {"geometry": case["expected"], "errors": []}, case["name"]
