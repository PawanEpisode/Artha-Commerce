"""
Machine-checked API contract drift test for Question Bank (F-06).
Asserts that `docs/QB-API-CONTRACT.md` and the implementation stay completely in sync.
"""

import dataclasses
import re
from pathlib import Path

import pytest

from modules.questionbank import urls, views
from modules.questionbank.selectors import (
    PlayableOption,
    PlayableQuestion,
    QuestionCard,
    ReviewQuestion,
)

pytestmark = pytest.mark.django_db

DOC = Path(__file__).resolve().parents[5] / "docs" / "QB-API-CONTRACT.md"


@pytest.fixture(scope="module")
def doc():
    assert DOC.exists(), f"The contract page is missing: {DOC}"
    return DOC.read_text()


def section(doc_text: str, name: str) -> str:
    match = re.search(rf"<!-- contract:{name} -->\n(.*?)\n<!-- /contract:{name} -->", doc_text, re.S)
    assert match, f"No <!-- contract:{name} --> block in the contract page"
    return match.group(1).strip()


def keys(doc_text: str, name: str) -> set[str]:
    return {k.strip() for k in section(doc_text, name).split(",") if k.strip()}


def rows(doc_text: str, name: str) -> list[list[str]]:
    return [
        [cell.strip().strip("`") for cell in line.strip("|").split("|")]
        for line in section(doc_text, name).splitlines()
        if line.startswith("|") and not set(line) <= set("| -")
    ][1:]


def implemented_endpoints():
    found = {}
    for pattern in urls.urlpatterns:
        view = pattern.callback.view_class
        assert issubclass(view, views.QuestionBankBaseView)
        for method in ("get", "post", "put", "patch", "delete"):
            if hasattr(view, method):
                found[(method.upper(), str(pattern.pattern))] = view
    return found


def test_the_endpoint_table_lists_exactly_the_implemented_endpoints(doc):
    documented = {(method, path) for method, path, *_ in rows(doc, "endpoints")}
    assert documented == set(implemented_endpoints())


def test_each_endpoint_documents_its_throttle_scope(doc, rf):
    for method, path, _purpose, scope in rows(doc, "endpoints"):
        view_cls = implemented_endpoints()[(method, path)]
        view = view_cls()
        view.request = rf.generic(method, "/")
        assert view.throttle_scope == scope, f"{method} {path}"


def test_throttle_rates_match_the_page(doc, settings):
    text = doc.split("Throttle scopes:")[1].split("\n")[0]
    rates = settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]
    for scope, number, unit in re.findall(r"`(qb_\w+|legal_notice)` (\d+) per (minute|hour|day)", text):
        expected_unit = "min" if unit == "minute" else ("hour" if unit == "hour" else "day")
        assert rates[scope] == f"{number}/{expected_unit}", scope


def test_playable_payload_keys_match(doc):
    expected = keys(doc, "playable-keys")
    actual = {f.name for f in dataclasses.fields(PlayableQuestion)}
    assert actual == expected


def test_playable_option_keys_match(doc):
    expected = keys(doc, "playable-option-keys")
    actual = {f.name for f in dataclasses.fields(PlayableOption)}
    assert actual == expected


def test_review_payload_keys_match(doc):
    expected = keys(doc, "review-keys")
    actual = {f.name for f in dataclasses.fields(ReviewQuestion)}
    assert actual == expected


def test_card_keys_match(doc):
    expected = keys(doc, "card-keys")
    actual = {f.name for f in dataclasses.fields(QuestionCard)}
    assert actual == expected
