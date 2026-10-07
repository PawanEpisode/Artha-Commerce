"""Text anchoring, shared with `anchors.test.ts` through `anchoring_cases.json`."""

import json
import random
from pathlib import Path

import pytest

from modules.notes.domain import anchoring as a

FIXTURES = json.loads((Path(__file__).parent / "fixtures" / "anchoring_cases.json").read_text())


@pytest.mark.parametrize("case", FIXTURES["normalise"], ids=lambda c: c["name"])
def test_normalise_for_match(case):
    n = a.normalise_for_match(case["input"])
    assert (n.text, list(n.starts), list(n.ends)) == (case["text"], case["starts"], case["ends"])
    assert len(n.text) == len(n.starts) == len(n.ends)


@pytest.mark.parametrize("case", FIXTURES["selector"], ids=lambda c: c["name"])
def test_make_selector(case):
    assert a.make_selector(case["page_text"], case["start"], case["end"]) == case["expected"]


@pytest.mark.parametrize("case", FIXTURES["locate"], ids=lambda c: c["name"])
def test_locate_quote(case):
    got = a.locate_quote(
        case["page_text"], case["quote_exact"], case["quote_prefix"], case["quote_suffix"], case["hint_start"]
    )
    if case["result"] is None:
        assert got is None
        assert case["expect_text"] is None
        return
    assert got is not None
    assert list(got) == case["result"]
    assert case["page_text"][got[0] : got[1]] == case["expect_text"]
    assert got[2] >= a.MIN_SCORE


def test_an_empty_selection_is_refused():
    with pytest.raises(ValueError):
        a.make_selector("abc", 2, 2)


def test_a_selector_finds_itself_wherever_the_page_text_moves():
    page = "".join(random.Random(3).choice("abcdefghij  \n") for _ in range(900))
    sel = a.make_selector(page, 400, 440)
    moved = "HEADER LINE\n\n" + page
    got = a.locate_quote(moved, sel["quote_exact"], sel["quote_prefix"], sel["quote_suffix"], sel["text_start"])
    assert got is not None and got[2] == 1.0
    assert " ".join(moved[got[0] : got[1]].split()) == " ".join(page[400:440].split())


def test_the_original_range_covers_the_whole_matched_text_including_removed_characters():
    page = "xx deduc-\ntion of tax yy"
    got = a.locate_quote(page, "deduction of tax")
    assert got is not None
    assert page[got[0] : got[1]] == "deduc-\ntion of tax"
