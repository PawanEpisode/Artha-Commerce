import json
from datetime import date
from pathlib import Path

import pytest

from modules.coverage.domain import formula as f

CASES = json.loads((Path(__file__).parent / "fixtures" / "formula_cases.json").read_text())


@pytest.mark.parametrize("case", CASES["cases"], ids=[c["name"] for c in CASES["cases"]])
def test_components_match_shared_fixtures(case):
    w = f.Weights(**CASES["weights"])
    got = f.compute_components(f.ChapterInputs(**case["inputs"]), w)
    assert got == f.Components(**case["expected"])


def test_custom_weights_change_the_result():
    inputs = f.ChapterInputs(topics_total=2, topics_done=2, practice_count=0, revision_count=0, mock_count=0)
    assert f.compute_components(inputs, f.Weights(100, 0, 0, 0)).coverage == 100
    assert f.compute_components(inputs, f.Weights(0, 50, 50, 0)).coverage == 0


def test_all_zero_applicable_weights_fall_back_to_read():
    inputs = f.ChapterInputs(
        topics_total=2, topics_done=1, practice_count=0, revision_count=0, mock_count=0, target_practice_sets=1
    )
    assert f.compute_components(inputs, f.Weights(0, 100, 0, 0)).coverage == 0  # practice is applicable, so used
    only_practice_na = f.ChapterInputs(
        topics_total=2,
        topics_done=1,
        practice_count=0,
        revision_count=0,
        mock_count=0,
        target_practice_sets=0,
        target_revisions=0,
        target_mocks=0,
    )
    assert f.compute_components(only_practice_na, f.Weights(0, 100, 0, 0)).coverage == 50


@pytest.mark.parametrize(
    ("kwargs", "expected"),
    [
        (
            dict(read_pct=0, coverage_pct=0, practice_count=0, revision_count=0, any_activity=False),
            f.STATUS_NOT_STARTED,
        ),
        (dict(read_pct=0, coverage_pct=0, practice_count=0, revision_count=0, any_activity=True), f.STATUS_READING),
        (dict(read_pct=40, coverage_pct=16, practice_count=0, revision_count=0, any_activity=True), f.STATUS_READING),
        (dict(read_pct=100, coverage_pct=40, practice_count=0, revision_count=0, any_activity=True), f.STATUS_READING),
        (
            dict(read_pct=100, coverage_pct=70, practice_count=1, revision_count=0, any_activity=True),
            f.STATUS_PRACTISED,
        ),
        (
            dict(read_pct=100, coverage_pct=70, practice_count=1, revision_count=1, any_activity=True),
            f.STATUS_REVISED_ONCE,
        ),
        (
            dict(read_pct=100, coverage_pct=80, practice_count=1, revision_count=2, any_activity=True),
            f.STATUS_REVISED_TWICE_PLUS,
        ),
        (
            dict(read_pct=100, coverage_pct=85, practice_count=1, revision_count=2, any_activity=True),
            f.STATUS_EXAM_READY,
        ),
        (
            dict(read_pct=100, coverage_pct=95, practice_count=1, revision_count=1, any_activity=True),
            f.STATUS_REVISED_ONCE,
        ),
    ],
)
def test_status_rules_first_match_wins(kwargs, expected):
    assert f.derive_status(**kwargs) == expected


def test_marks_weight_coalesces():
    assert f.marks_weight(10, 20) == 15
    assert f.marks_weight(None, 8) == 8
    assert f.marks_weight(6, None) == 6
    assert f.marks_weight(None, None) == 1


def test_rollup_simple_weighted_and_exclusion():
    rows = [
        f.RollupRow(100, 15, False, f.STATUS_EXAM_READY),
        f.RollupRow(0, 5, False, f.STATUS_NOT_STARTED),
        f.RollupRow(50, 100, True, f.STATUS_READING),  # excluded: ignored everywhere
    ]
    r = f.rollup(rows)
    assert (r.pct_simple, r.pct_weighted, r.chapters_total, r.chapters_done) == (50, 75, 2, 1)
    assert f.rollup([]) == f.RollupResult(0, 0, 0, 0)
    assert f.rollup([f.RollupRow(10, 1, True, f.STATUS_READING)]).chapters_total == 0


def test_higher_marks_chapter_counts_more_in_weighted_view():
    heavy_done = [f.RollupRow(100, 15, False, ""), f.RollupRow(0, 5, False, "")]
    light_done = [f.RollupRow(0, 15, False, ""), f.RollupRow(100, 5, False, "")]
    assert f.rollup(heavy_done).pct_weighted > f.rollup(light_done).pct_weighted
    assert f.rollup(heavy_done).pct_simple == f.rollup(light_done).pct_simple


def test_next_revision_due_follows_the_schedule_and_repeats_the_last_gap():
    start = date(2026, 10, 4)
    days = [3, 7, 21, 45]
    assert f.next_revision_due(start, 1, days) == date(2026, 10, 7)
    assert f.next_revision_due(start, 2, days) == date(2026, 10, 11)
    assert f.next_revision_due(start, 4, days) == date(2026, 11, 18)
    assert f.next_revision_due(start, 9, days) == date(2026, 11, 18)
    assert f.next_revision_due(start, 0, days) is None


def test_validators():
    assert f.weights_valid(f.Weights(40, 30, 20, 10))
    assert not f.weights_valid(f.Weights(40, 30, 20, 20))
    assert not f.weights_valid(f.Weights(-10, 60, 30, 20))
    assert f.revision_days_valid([3, 7])
    assert not f.revision_days_valid([])
    assert not f.revision_days_valid([0])
    assert not f.revision_days_valid([1] * 9)
    assert not f.revision_days_valid([True])
