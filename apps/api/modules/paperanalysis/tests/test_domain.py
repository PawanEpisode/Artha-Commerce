"""
Unit and property tests for F-11 pure domain algorithms.
"""

import uuid
from decimal import Decimal

import pytest

from modules.paperanalysis.domain.aggregate import (
    SittingMark,
    calculate_chapter_aggregates,
)
from modules.paperanalysis.domain.apportion import apportion
from modules.paperanalysis.domain.backtest import (
    PaperFoldMark,
    run_walk_forward_backtest,
)
from modules.paperanalysis.domain.comparability import (
    ComparabilityStatus,
    evaluate_comparability,
)
from modules.paperanalysis.domain.effective import (
    calculate_choice_group_attemptable,
    calculate_effective_marks,
    is_practical_format_or_nature,
)
from modules.paperanalysis.domain.explain import (
    lint_copy,
    render_reason,
)
from modules.paperanalysis.domain.planner import (
    PlannerChapterCandidate,
    compute_personal_pace,
    plan_n_days,
)
from modules.paperanalysis.domain.scoring import (
    ChapterInput,
    PaperSittingInput,
    SubjectScoringInput,
    score_subject,
)
from modules.paperanalysis.domain.types import PlanInputs
from modules.syllabus.selectors import MapEdge


def test_apportion_exact_sum_and_remainder():
    # Example from PRD: 14 marks, weights 0.6 and 0.4 -> 8.5 and 5.5
    res = apportion(Decimal("14.0"), [0.6, 0.4])
    assert res == [Decimal("8.5"), Decimal("5.5")]
    assert sum(res) == Decimal("14.0")


def test_apportion_properties():
    marks_cases = [Decimal("10.0"), Decimal("15.5"), Decimal("7.0"), Decimal("25.0")]
    weights_cases = [
        [0.5, 0.5],
        [0.7, 0.2, 0.1],
        [1.0, 1.0, 1.0],
        [0.33, 0.33, 0.34],
    ]
    for m in marks_cases:
        for w in weights_cases:
            allocs = apportion(m, w)
            assert sum(allocs) == m
            # No part differs from ideal by more than step (0.5)
            total_w = sum(w)
            for i, a in enumerate(allocs):
                ideal = m * Decimal(str(w[i])) / Decimal(str(total_w))
                assert abs(a - ideal) <= Decimal("0.5")


def test_effective_marks():
    # Choice group: any 4 of 5 with 14 marks each -> 11.20
    eff = calculate_effective_marks(Decimal("14.0"), pick_n=4, of_m=5)
    assert eff == Decimal("11.20")

    # Outside choice group
    assert calculate_effective_marks(Decimal("10.0")) == Decimal("10.0")

    # Attemptable marks
    q_marks = [Decimal("14.0")] * 5
    attemptable = calculate_choice_group_attemptable(4, 5, q_marks)
    assert attemptable == Decimal("56.0")


def test_theory_practical_classification():
    assert is_practical_format_or_nature("practical", None) is True
    assert is_practical_format_or_nature("descriptive", "practical") is True
    assert is_practical_format_or_nature("descriptive", "application") is True
    assert is_practical_format_or_nature("mcq", "theory") is False
    assert is_practical_format_or_nature("descriptive", "concept") is False


def test_aggregates_and_trend():
    # Fewer than 5 sittings: trend is None
    sittings_4 = [
        SittingMark("2025-05", Decimal("18.0"), True),
        SittingMark("2024-11", Decimal("6.0"), True),
        SittingMark("2024-05", Decimal("0.0"), False),
        SittingMark("2023-11", Decimal("12.0"), True),
    ]
    agg4 = calculate_chapter_aggregates(sittings_4)
    assert agg4.papers_considered == 4
    assert agg4.asked_n == 3
    assert agg4.avg_effective == Decimal("9.00")
    assert agg4.avg_when_asked == Decimal("12.00")
    assert agg4.max_effective == Decimal("18.0")
    assert agg4.trend is None
    assert agg4.last_asked_term_code == "2025-05"

    # 6 sittings: trend is calculated
    sittings_6 = [
        SittingMark("2025-05", Decimal("18.0"), True),
        SittingMark("2024-11", Decimal("12.0"), True),
        SittingMark("2024-05", Decimal("15.0"), True),
        SittingMark("2023-11", Decimal("6.0"), True),
        SittingMark("2023-05", Decimal("6.0"), True),
        SittingMark("2022-11", Decimal("0.0"), False),
    ]
    agg6 = calculate_chapter_aggregates(sittings_6)
    assert agg6.papers_considered == 6
    assert agg6.trend is not None
    # Recent 3: 18, 12, 15 (mean 15.0). Prev 3: 6, 6, 0 (mean 4.0). Mean all: 9.5. r = 11.0 / 9.5 = 1.0 (clamped)
    assert agg6.trend > Decimal("0")


def test_comparability():
    curr_scheme = uuid.uuid4()
    old_scheme = uuid.uuid4()
    curr_chap = uuid.uuid4()
    old_chap1 = uuid.uuid4()
    old_chap2 = uuid.uuid4()

    # Native
    c_nat = evaluate_comparability(curr_chap, curr_scheme, curr_scheme, [])
    assert c_nat.status == ComparabilityStatus.NATIVE
    assert c_nat.carry_weight == 1.0

    # Carried (same/merged)
    edge_carried = [
        MapEdge(old_chap1, curr_chap, "same", 1.0, False, 1.0),
        MapEdge(old_chap2, curr_chap, "merged", 1.0, False, 0.9),
    ]
    c_car = evaluate_comparability(curr_chap, curr_scheme, old_scheme, edge_carried)
    assert c_car.status == ComparabilityStatus.CARRIED
    assert c_car.carry_weight == 0.7
    assert set(c_car.source_chapter_ids) == {old_chap1, old_chap2}

    # Restructured (split or needs_review)
    edge_split = [MapEdge(old_chap1, curr_chap, "split", 0.5, False, 0.5)]
    c_split = evaluate_comparability(curr_chap, curr_scheme, old_scheme, edge_split)
    assert c_split.status == ComparabilityStatus.RESTRUCTURED
    assert c_split.carry_weight == 0.0


def test_scoring_engine_determinism_and_tiers():
    c1 = uuid.uuid4()
    c2 = uuid.uuid4()
    c3 = uuid.uuid4()

    sittings_c1 = [
        PaperSittingInput(uuid.uuid4(), "2025-05", "exam", 0, 18.0),
        PaperSittingInput(uuid.uuid4(), "2024-11", "exam", 1, 14.0),
        PaperSittingInput(uuid.uuid4(), "2024-05", "exam", 2, 16.0),
        PaperSittingInput(uuid.uuid4(), "2023-11", "exam", 3, 10.0),
        PaperSittingInput(uuid.uuid4(), "2023-05", "exam", 4, 12.0),
        PaperSittingInput(uuid.uuid4(), "2022-11", "exam", 5, 8.0),
    ]
    sittings_c2 = [
        PaperSittingInput(uuid.uuid4(), "2025-05", "exam", 0, 8.0),
        PaperSittingInput(uuid.uuid4(), "2024-11", "exam", 1, 6.0),
        PaperSittingInput(uuid.uuid4(), "2024-05", "exam", 2, 4.0),
        PaperSittingInput(uuid.uuid4(), "2023-11", "exam", 3, 5.0),
        PaperSittingInput(uuid.uuid4(), "2023-05", "exam", 4, 6.0),
        PaperSittingInput(uuid.uuid4(), "2022-11", "exam", 5, 0.0),
    ]
    sittings_c3 = [
        PaperSittingInput(uuid.uuid4(), "2025-05", "exam", 0, 0.0),
        PaperSittingInput(uuid.uuid4(), "2024-11", "exam", 1, 2.0),
        PaperSittingInput(uuid.uuid4(), "2024-05", "exam", 2, 0.0),
        PaperSittingInput(uuid.uuid4(), "2023-11", "exam", 3, 0.0),
        PaperSittingInput(uuid.uuid4(), "2023-05", "exam", 4, 0.0),
        PaperSittingInput(uuid.uuid4(), "2022-11", "exam", 5, 0.0),
    ]

    inp = SubjectScoringInput(
        subject_key="taxation",
        total_subject_marks=100.0,
        chapters=[
            ChapterInput(c1, "itc", "Input Tax Credit", "Section B", 1, sittings=sittings_c1, coverage_fraction=0.2, practice_answered=20, practice_correct=9),
            ChapterInput(c2, "res", "Residential Status", "Section A", 2, sittings=sittings_c2, coverage_fraction=0.5, practice_answered=15, practice_correct=10),
            ChapterInput(c3, "exempt", "Exempt Incomes", "Section A", 3, sittings=sittings_c3, coverage_fraction=0.8, practice_answered=5, practice_correct=4),
        ],
        days_left=45,
    )

    scored1 = score_subject(inp)
    scored2 = score_subject(inp)

    # Determinism: byte identical outputs
    assert len(scored1) == 3
    assert [s.score for s in scored1] == [s.score for s in scored2]
    assert [s.tier for s in scored1] == [s.tier for s in scored2]

    # Chapter 1 is the heaviest
    assert scored1[0].chapter_key == "itc"
    assert scored1[0].tier == "core"
    assert scored1[0].rank == 1
    assert scored1[0].confidence == "high"


def test_planner_algorithm_safeguard_and_budget():
    c1 = uuid.uuid4()
    c2 = uuid.uuid4()
    c3 = uuid.uuid4()

    candidates = [
        PlannerChapterCandidate(c1, "ch1", "tax", "Chapter 1", 1, expected_marks=18.0, coverage_fraction=0.2, accuracy=0.5, base_minutes=180, effort_basis="topic count", confidence="high"),
        PlannerChapterCandidate(c2, "ch2", "tax", "Chapter 2", 2, expected_marks=10.0, coverage_fraction=0.1, accuracy=0.6, base_minutes=120, effort_basis="topic count", confidence="high"),
        PlannerChapterCandidate(c3, "ch3", "tax", "Chapter 3", 3, expected_marks=4.0, coverage_fraction=0.7, accuracy=0.8, base_minutes=60, effort_basis="topic count", confidence="high"),
    ]

    inputs = PlanInputs(days=5, hours_per_day=4.0, subject_keys=["tax"])
    preview = plan_n_days(inputs, candidates)

    assert preview.hours_used <= preview.budget_hours
    assert preview.budget_hours == 18.0  # 5 * 4 * 0.9 = 18.0
    assert len(preview.items) >= 1
    assert preview.covered_share > 0.0


def test_personal_pace():
    # Student with tracked minutes vs estimate
    history = [(60, 60), (90, 60), (45, 30)]  # took 1.5x on average
    pace_ctx = compute_personal_pace(history)
    assert pace_ctx.pace > 1.0
    assert pace_ctx.pace_basis == "at your own pace"


def test_walk_forward_backtest():
    cid1, cid2, cid3 = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    sittings: list[PaperFoldMark] = []
    # Create 6 exam papers across terms
    for term in ["2023-05", "2023-11", "2024-05", "2024-11", "2025-05", "2025-11"]:
        pid = uuid.uuid4()
        sittings.append(PaperFoldMark(pid, term, term, "exam", cid1, 15.0))
        sittings.append(PaperFoldMark(pid, term, term, "exam", cid2, 10.0))
        sittings.append(PaperFoldMark(pid, term, term, "exam", cid3, 5.0))

    bt = run_walk_forward_backtest(sittings, k_fraction=0.33)
    assert bt.folds == 3  # papers 3, 4, 5
    assert bt.lift >= 1.0


def test_explain_copy_lint():
    # Valid reason
    sentence = render_reason("asked_in_window", {"max": 18.0, "asked_n": 5, "window_n": 6})
    assert "Carried up to 18.0 marks" in sentence

    # Forbidden phrase check
    with pytest.raises(ValueError, match="Forbidden phrase 'guaranteed'"):
        lint_copy("This chapter is guaranteed to come")

    with pytest.raises(ValueError, match="Forbidden phrase 'sure shot'"):
        lint_copy("This is a sure shot question")

    with pytest.raises(ValueError, match="Forbidden phrase 'skip'"):
        lint_copy("You can skip this chapter")
