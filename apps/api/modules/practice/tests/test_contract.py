"""
Machine-checked API contract drift test for Practice Engine (F-06 S10-S12, E-F06-1).
Asserts that `docs/QB-API-CONTRACT.md` and the implementation stay completely in sync.
"""

from __future__ import annotations

import dataclasses
import re
from pathlib import Path

import pytest

from modules.practice import urls, views
from modules.practice.selectors import (
    ChapterProgress,
    SessionItemView,
    SessionView,
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
        assert issubclass(view, views.PracticeBaseView)
        for method in ("get", "post", "put", "patch", "delete"):
            if hasattr(view, method):
                found[(method.upper(), str(pattern.pattern))] = view
    return found


def test_the_endpoint_table_lists_exactly_the_implemented_endpoints(doc):
    documented = {(method, path) for method, path, *_ in rows(doc, "practice-endpoints")}
    assert documented == set(implemented_endpoints())


def test_each_endpoint_documents_its_throttle_scope(doc, rf):
    for method, path, _purpose, scope in rows(doc, "practice-endpoints"):
        view_cls = implemented_endpoints()[(method, path)]
        view = view_cls()
        view.request = rf.generic(method, "/")
        assert view.throttle_scope == scope, f"{method} {path}"


def test_session_view_keys_match(doc):
    expected = keys(doc, "practice-session-view-keys")
    actual = {f.name for f in dataclasses.fields(SessionView)}
    assert actual == expected


def test_session_item_view_keys_match(doc):
    expected = keys(doc, "practice-session-item-view-keys")
    actual = {f.name for f in dataclasses.fields(SessionItemView)}
    assert actual == expected


def test_chapter_progress_keys_match(doc):
    expected = keys(doc, "practice-chapter-progress-keys")
    actual = {f.name for f in dataclasses.fields(ChapterProgress)}
    assert actual == expected
