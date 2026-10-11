"""The chapter recall pass rule (pure): boundary cases from `vectors/chapter_pass_cases.json` plus properties."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from modules.recall.domain import chapter_pass as cp

CASES = json.loads((Path(__file__).parent / "vectors" / "chapter_pass_cases.json").read_text())


def t(text: str) -> datetime:
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


@pytest.mark.parametrize("case", CASES["evaluate"], ids=lambda c: f"{c['ok']}of{c['set_size']}")
def test_the_pass_rule(case):
    result = cp.evaluate(case["set_size"], case["ok"])
    assert (result.passed, result.eligible) == (case["passed"], case["eligible"])


@pytest.mark.parametrize("case", CASES["window"], ids=lambda c: c["reviewed_at"])
def test_a_review_counts_while_it_is_younger_than_seven_days(case):
    assert cp.in_window(t(case["reviewed_at"]), t(case["now"])) is case["in"]


@pytest.mark.parametrize("case", CASES["cooldown"], ids=lambda c: str(c["last"]))
def test_one_announced_pass_per_seven_days(case):
    last = t(case["last"]) if case["last"] else None
    assert cp.cooldown_over(last, t(case["now"])) is case["over"]


def test_four_cards_can_never_pass_and_five_can():
    assert not cp.evaluate(4, 4).passed
    assert cp.evaluate(5, 4).passed


def test_79_and_80_percent_are_on_either_side_of_the_line():
    assert not cp.evaluate(100, 79).passed and cp.evaluate(100, 80).passed
    assert cp.evaluate(100, 80).coverage_of_set == 0.8


def test_six_days_in_and_seven_days_out():
    now = datetime(2026, 10, 11, 12, tzinfo=UTC)
    assert cp.in_window(now - timedelta(days=6), now)
    assert not cp.in_window(now - timedelta(days=7), now)


def test_coverage_of_an_empty_set_is_zero_and_nothing_divides_by_zero():
    r = cp.evaluate(0, 0)
    assert (r.coverage_of_set, r.passed, r.eligible) == (0.0, False, False)


def test_more_reviewed_cards_than_the_set_holds_is_clamped():
    r = cp.evaluate(5, 50)
    assert r.reviewed_ok == 5 and r.coverage_of_set == 1.0


@pytest.mark.parametrize("size", range(0, 60))
def test_passing_is_monotonic_in_the_reviewed_count(size):
    results = [cp.evaluate(size, ok).passed for ok in range(size + 1)]
    assert results == sorted(results)  # once it passes, more reviewed cards never un-pass it
