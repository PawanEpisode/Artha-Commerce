"""
Runs the shared conformance corpus (`richtext_cases.json`). The web twin of the linter runs the same file, so the two
implementations cannot drift: change a rule here and a case there in the same pull request. `repeat` cases build long
bodies from a unit so the file stays small.
"""

import json
import uuid
from pathlib import Path

import pytest

from core import richtext

CORPUS = json.loads((Path(__file__).parent / "richtext_cases.json").read_text(encoding="utf-8"))
CASES = CORPUS["cases"]


def body_of(case: dict) -> str:
    repeat = case.get("repeat")
    return repeat["unit"] * repeat["times"] if repeat else case["markdown"]


def test_the_corpus_is_the_version_the_code_expects_and_is_not_empty():
    assert CORPUS["version"] == richtext.CORPUS_VERSION
    assert len(CASES) >= 60
    assert len({c["id"] for c in CASES}) == len(CASES)


@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_lint_matches_the_corpus(case):
    issues = richtext.lint(body_of(case), case["profile"])
    assert sorted({i.code for i in issues if i.severity == "error"}) == case["errors"]
    assert sorted({i.code for i in issues if i.severity == "warning"}) == case["warnings"]


@pytest.mark.parametrize("case", [c for c in CASES if "text" in c], ids=[c["id"] for c in CASES if "text" in c])
def test_plain_text_matches_the_corpus(case):
    assert richtext.plain_text(body_of(case)) == case["text"]


@pytest.mark.parametrize(
    "case", [c for c in CASES if "sanitised" in c], ids=[c["id"] for c in CASES if "sanitised" in c]
)
def test_sanitise_matches_the_corpus(case):
    assert richtext.sanitise(body_of(case)) == case["sanitised"]


def test_issues_carry_a_line_number_where_one_exists():
    issues = richtext.lint("fine\n\n[x](javascript:alert(1))", "note")
    assert [(i.code, i.line) for i in issues] == [("link_scheme", 3)]


def test_attachment_refs_lists_uploaded_images_in_order_and_skips_code():
    a, b = uuid.uuid4(), uuid.uuid4()
    body = f"![one](attachment:{a})\n\n```\n![x](attachment:{uuid.uuid4()})\n```\n\n![](attachment:{b})"
    refs = richtext.attachment_refs(body)
    assert [(r.attachment_id, r.alt) for r in refs] == [(a, "one"), (b, "")]


def test_sanitise_is_idempotent_and_never_touches_visible_text():
    text = "a\r\nb ‮ c\x00 क्‍ष"
    once = richtext.sanitise(text)
    assert richtext.sanitise(once) == once
    assert "क्‍ष" in once


def test_unknown_profile_is_a_programming_error():
    with pytest.raises(KeyError):
        richtext.lint("x", "nope")
