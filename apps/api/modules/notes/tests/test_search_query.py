"""Reference-aware query preparation (ERD 6.3) shared with `search-query.test.ts`, and language detection."""

import json
from pathlib import Path

import pytest

from modules.notes.domain import lang, search_query

FIXTURES = json.loads((Path(__file__).parent / "fixtures" / "search_query_cases.json").read_text())


@pytest.mark.parametrize("case", FIXTURES["prepare"], ids=lambda c: c["input"] or "empty")
def test_prepare_query(case):
    assert search_query.prepare_query(case["input"]) == case["expected"]


@pytest.mark.parametrize("case", FIXTURES["clean"], ids=lambda c: repr(c["input"][:12]))
def test_clean_query(case):
    assert search_query.clean_query(case["input"]) == case["expected"]


def test_the_r1_behaviour_is_unchanged():
    assert search_query.prepare_query("section 16(2) credit") == 'section "16(2)" credit'
    assert search_query.prepare_query("  gst   itc ") == "gst itc"


def test_a_prepared_query_is_stable():
    for case in FIXTURES["prepare"]:
        once = search_query.prepare_query(case["input"])
        if '"abc' not in once:  # an unbalanced quote is the one input the quoting cannot settle
            assert search_query.prepare_query(once) == once


def test_the_language_helpers_are_reexported_for_existing_callers():
    assert search_query.detect_lang is lang.detect_lang
    assert search_query.config_for is lang.config_for
    assert search_query.config_for_text is lang.detect_search_config


@pytest.mark.parametrize(
    ("text", "label", "config"),
    [
        ("input tax credit", "en", "english"),
        ("", "en", "english"),
        ("123 456 !?", "en", "english"),
        ("आगत कर क्रेडिट नियम", "hi", "simple"),
        ("input tax credit rule कर क्रेडिट नियम", "mixed", "simple"),
        ("ITC यानी input tax credit", "en", "english"),  # 19% Devanagari: still mostly English
        ("Section 17(5) आगत कर क्रेडिट का दावा केवल", "hi", "simple"),  # digits and punctuation are not letters
    ],
)
def test_detect_lang_and_search_config(text, label, config):
    assert lang.detect_lang(text) == label
    assert lang.detect_search_config(text) == config


def test_the_thirty_percent_edge():
    # 10 letters in total: 3 Devanagari is exactly 30% (stays english), 4 is above it (simple)
    assert lang.detect_search_config("abcdefg" + "कखग") == "english"
    assert lang.detect_search_config("abcdef" + "कखगघ") == "simple"
    assert lang.devanagari_share("abcdef कखगघ") == pytest.approx(0.4)
