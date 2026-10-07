"""Chapter inheritance for marks (FR-F03-30), shared with `chapter-inheritance.test.ts` through `inheritance_cases.json`."""

import json
from pathlib import Path

import pytest

from modules.notes.domain import chapter_inheritance as inh

FIXTURES = json.loads((Path(__file__).parent / "fixtures" / "inheritance_cases.json").read_text())


@pytest.mark.parametrize("case", FIXTURES["effective"], ids=lambda c: c["name"])
def test_effective_link(case):
    chapter, source = inh.effective_link(case["page"], case["explicit"], case["ranges"], case["default"])
    assert {"chapter": chapter, "source": source} == case["expected"]
    assert source in inh.SOURCES


@pytest.mark.parametrize("case", FIXTURES["validate"], ids=lambda c: c["name"])
def test_validate_ranges(case):
    assert inh.validate_ranges(case["ranges"]) == case["expected"]


@pytest.mark.parametrize("case", FIXTURES["outline"], ids=lambda c: c["name"])
def test_ranges_from_outline(case):
    assert inh.ranges_from_outline(case["outline"], case["page_count"]) == case["expected"]


def test_suggested_ranges_are_always_valid_and_inside_the_document():
    for case in FIXTURES["outline"]:
        ranges = inh.ranges_from_outline(case["outline"], case["page_count"])
        assert inh.validate_ranges(ranges) is None
        assert all(1 <= r["page_from"] <= r["page_to"] <= case["page_count"] for r in ranges)
