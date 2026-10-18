"""
Pure walk-forward back-test engine for F-11.
Reference: PRD 6.1, FR-F11-30, and ERD 3.5.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID


@dataclass(frozen=True)
class PaperFoldMark:
    paper_id: UUID
    term_code: str
    term_sort: str
    paper_kind: str
    chapter_id: UUID
    effective_marks: float


@dataclass(frozen=True)
class BacktestResult:
    papers_used: int
    folds: int
    marks_captured: float
    baseline_flat: float
    lift: float
    metrics: dict[str, Any]


def run_walk_forward_backtest(
    all_sittings: list[PaperFoldMark],
    k_fraction: float = 0.30,
    min_folds: int = 1,
) -> BacktestResult:
    """
    Executes walk-forward back-testing:
    For each sitting starting from the 4th sitting onward:
      - Train on all earlier sittings
      - Score top-k chapters
      - Measure marks captured in the test sitting
      - Compare to flat baseline
    """
    # Group sittings by paper_id, ordered by term_sort ascending
    papers_order: dict[UUID, tuple[str, str]] = {}
    paper_chapter_marks: dict[UUID, dict[UUID, float]] = {}

    for row in all_sittings:
        if row.paper_id not in papers_order:
            papers_order[row.paper_id] = (row.term_sort, row.term_code)
            paper_chapter_marks[row.paper_id] = {}
        paper_chapter_marks[row.paper_id][row.chapter_id] = row.effective_marks

    sorted_papers = sorted(papers_order.items(), key=lambda it: it[1][0])
    num_papers = len(sorted_papers)

    if num_papers < 4:
        return BacktestResult(
            papers_used=num_papers,
            folds=0,
            marks_captured=0.0,
            baseline_flat=k_fraction,
            lift=1.0,
            metrics={"error": "Fewer than 4 papers for back-testing"},
        )

    all_chapters = {row.chapter_id for row in all_sittings}
    num_chapters = len(all_chapters)
    k_count = max(1, int(round(num_chapters * k_fraction)))

    fold_captures: list[float] = []
    fold_details: list[dict[str, Any]] = []

    # From 4th paper onward (index 3 to num_papers - 1)
    for test_idx in range(3, num_papers):
        train_paper_ids = [sorted_papers[j][0] for j in range(test_idx)]
        test_paper_id = sorted_papers[test_idx][0]
        test_term_code = sorted_papers[test_idx][1][1]

        # Aggregate train marks per chapter
        chapter_train_sum: dict[UUID, float] = {cid: 0.0 for cid in all_chapters}
        for pid in train_paper_ids:
            for cid, marks in paper_chapter_marks[pid].items():
                chapter_train_sum[cid] = chapter_train_sum.get(cid, 0.0) + marks

        # Sort chapters by train marks desc
        ranked_chapters = sorted(all_chapters, key=lambda cid: -chapter_train_sum.get(cid, 0.0))
        top_k_chapters = set(ranked_chapters[:k_count])

        # Test paper marks
        test_marks = paper_chapter_marks[test_paper_id]
        total_test_marks = sum(test_marks.values())
        if total_test_marks <= 0:
            continue

        captured_test_marks = sum(marks for cid, marks in test_marks.items() if cid in top_k_chapters)
        capture_ratio = captured_test_marks / total_test_marks
        fold_captures.append(capture_ratio)
        fold_details.append({
            "fold": len(fold_captures),
            "test_term": test_term_code,
            "train_papers_n": len(train_paper_ids),
            "captured_share": round(capture_ratio, 4),
        })

    if not fold_captures:
        return BacktestResult(
            papers_used=num_papers,
            folds=0,
            marks_captured=0.0,
            baseline_flat=k_fraction,
            lift=1.0,
            metrics={"error": "No non-empty test folds"},
        )

    mean_captured = sum(fold_captures) / len(fold_captures)
    lift = mean_captured / k_fraction if k_fraction > 0 else 1.0

    return BacktestResult(
        papers_used=num_papers,
        folds=len(fold_captures),
        marks_captured=round(mean_captured, 4),
        baseline_flat=round(k_fraction, 4),
        lift=round(lift, 3),
        metrics={
            "v": 1,
            "k_fraction": k_fraction,
            "k_count": k_count,
            "folds": fold_details,
        },
    )
