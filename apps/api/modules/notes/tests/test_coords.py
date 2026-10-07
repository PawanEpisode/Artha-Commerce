"""Coordinate maths shared with `coords.test.ts` through `coords_cases.json`."""

import json
from pathlib import Path

import pytest

from modules.notes.domain import coords as c

FIXTURES = json.loads((Path(__file__).parent / "fixtures" / "coords_cases.json").read_text())


def _ids(case):
    return case["name"]


@pytest.mark.parametrize("case", FIXTURES["normalise"], ids=_ids)
def test_normalise_rect(case):
    assert c.normalise_rect(*case["pt"], *case["page"]) == case["expected"]


@pytest.mark.parametrize("case", FIXTURES["denormalise"], ids=_ids)
def test_denormalise_rect(case):
    assert c.denormalise_rect(case["rect"], *case["page"]) == pytest.approx(case["expected"])


@pytest.mark.parametrize("case", FIXTURES["rotate_rect"], ids=_ids)
def test_rotate_rect(case):
    assert c.rotate_rect(case["rect"], case["rotation"]) == case["expected"]


@pytest.mark.parametrize("case", FIXTURES["rotate_point"], ids=_ids)
def test_rotate_point(case):
    assert c.rotate_point(case["pt"], case["rotation"]) == case["expected"]


@pytest.mark.parametrize("case", FIXTURES["user_space"], ids=_ids)
def test_rect_to_user_space_for_the_export(case):
    assert c.rect_to_user_space(case["rect"], case["intrinsic_rotate"], *case["box"]) == case["expected"]


@pytest.mark.parametrize("rotation", [0, 90, 180, 270])
def test_unrotate_is_the_inverse(rotation):
    rect = [0.1, 0.2, 0.3, 0.05]
    assert c.unrotate_rect(c.rotate_rect(rect, rotation), rotation) == rect
    assert c.unrotate_point(c.rotate_point([0.25, 0.75], rotation), rotation) == [0.25, 0.75]


def test_four_quarter_turns_are_the_identity():
    rect = [0.12345, 0.2, 0.3, 0.05]
    for _ in range(4):
        rect = c.rotate_rect(rect, 90)
    assert rect == [0.12345, 0.2, 0.3, 0.05]


@pytest.mark.parametrize("bad", FIXTURES["invalid_rotations"])
def test_rotation_must_be_a_multiple_of_90(bad):
    with pytest.raises(ValueError):
        c.normalise_rotation(bad)


def test_view_size_swaps_at_quarter_turns():
    assert c.view_size(595, 842, 0) == (595, 842)
    assert c.view_size(595, 842, 90) == (842, 595)
    assert c.view_size(595, 842, -90) == (842, 595)
