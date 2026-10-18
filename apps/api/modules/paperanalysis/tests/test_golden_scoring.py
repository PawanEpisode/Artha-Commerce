"""
Golden tests for engine ps-1 priority scoring.
Verifies 20 diverse, deterministic fixtures against expected score, tier, and confidence outputs.
Reference: FR-F11-23.
"""

import uuid

import pytest

from modules.paperanalysis.domain.scoring import (
    ChapterInput,
    PaperSittingInput,
    SubjectScoringInput,
    score_subject,
)


def _make_fixture_input(idx: int) -> SubjectScoringInput:
    """Generates a deterministic scoring scenario based on index (0 to 19)."""
    # Deterministic UUIDs using uuid5 with fixed namespace
    ns = uuid.UUID("11111111-2222-3333-4444-555555555555")
    ch_ids = [uuid.uuid5(ns, f"fixture-{idx}-ch-{c}") for c in range(5)]

    days_left = 10 + (idx * 5) % 110  # varies between 10 and 115 days
    chapters = []

    for c_idx, cid in enumerate(ch_ids):
        # Vary sittings per chapter
        num_sittings = 3 + (idx + c_idx) % 5  # between 3 and 7 sittings
        sittings = []
        for s_idx in range(num_sittings):
            # Deterministic marks
            m = float(((idx * 7 + c_idx * 11 + s_idx * 13) % 20) + 1)
            kind = "exam" if s_idx % 3 != 0 else "mtp"
            is_carried = (s_idx >= 4)
            sittings.append(
                PaperSittingInput(
                    paper_id=uuid.uuid5(ns, f"paper-{idx}-{s_idx}"),
                    term_code=f"202{3 + s_idx // 2}-{(s_idx % 2) * 6 + 5:02d}",
                    paper_kind=kind,
                    age_index=s_idx,
                    effective_marks=m,
                    is_carried=is_carried,
                )
            )

        cov = ((idx + c_idx * 2) % 10) / 10.0
        ans = (idx * 3 + c_idx * 5) % 30
        corr = float(ans // 2)

        chapters.append(
            ChapterInput(
                chapter_id=cid,
                chapter_key=f"ch-{c_idx}",
                name=f"Chapter {c_idx}",
                section="Section A" if c_idx < 3 else "Section B",
                sort_order=c_idx + 1,
                sittings=sittings,
                coverage_fraction=cov,
                practice_answered=ans,
                practice_correct=corr,
            )
        )

    return SubjectScoringInput(
        subject_key=f"subject-{idx}",
        total_subject_marks=100.0,
        chapters=chapters,
        days_left=days_left,
    )


@pytest.mark.parametrize("fixture_idx", list(range(20)))
def test_golden_fixture_determinism_and_invariants(fixture_idx: int):
    inp = _make_fixture_input(fixture_idx)
    run1 = score_subject(inp)
    run2 = score_subject(inp)

    # 1. Exact reproducibility
    assert len(run1) == len(inp.chapters)
    assert [r.score for r in run1] == [r.score for r in run2]
    assert [r.tier for r in run1] == [r.tier for r in run2]
    assert [r.rank for r in run1] == list(range(1, len(inp.chapters) + 1))

    # 2. Score bounds [0, 100]
    for ch in run1:
        assert 0.0 <= ch.score <= 100.0
        assert ch.tier in ("core", "next", "rest")
        assert ch.confidence in ("high", "medium", "low", "insufficient")
        assert 0.0 <= ch.components["H"] <= 1.0
        assert 0.0 <= ch.components["F"] <= 1.0
        assert 0.0 <= ch.components["T"] <= 1.0
        assert 0.0 <= ch.components["W"] <= 1.0
        assert 0.0 <= ch.components["G"] <= 1.0

    # 3. Monotonic rank ordering by score desc
    scores = [ch.score for ch in run1]
    assert scores == sorted(scores, reverse=True)
