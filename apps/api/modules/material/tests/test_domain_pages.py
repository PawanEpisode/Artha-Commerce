"""
Unit tests for domain pages, term maths, and levels (F-12).
"""

import pytest

from modules.material.domain import levels, pages, term


def test_format_deep_link():
    assert pages.format_deep_link("https://icai.org/mod1.pdf", 41, 8) == "https://icai.org/mod1.pdf#page=49"
    assert pages.format_deep_link("https://icai.org/mod1.pdf#page=10", 41, 8) == "https://icai.org/mod1.pdf#page=49"
    assert pages.format_deep_link("https://icai.org/mod1.pdf", None, 8) == "https://icai.org/mod1.pdf"
    assert pages.format_deep_link(None, 41, 8) is None


def test_term_maths():
    assert term.term_to_ord("2026-05") == 2026 * 12 + 5
    assert term.ord_to_term(2026 * 12 + 5) == "2026-05"

    with pytest.raises(ValueError):
        term.term_to_ord("invalid-term")

    from_ord, to_ord = term.validate_term_range("2026-05", "2026-11")
    assert from_ord < to_ord

    with pytest.raises(ValueError):
        term.validate_term_range("2026-11", "2026-05")


def test_level_for_capabilities():
    assert levels.level_for([]) == 0
    assert levels.level_for(["metadata"]) == 0
    assert levels.level_for(["metadata", "link_out"]) == 1
    assert levels.level_for(["metadata", "link_out", "host_questions"]) == 1
    assert levels.level_for(["metadata", "link_out", "host_questions", "host_solutions"]) == 2
    assert levels.level_for(["metadata", "link_out", "host_questions", "host_solutions", "practice"]) == 3
    assert levels.level_for(["metadata", "link_out", "host_questions", "host_solutions", "practice", "public_seo"]) == 4
