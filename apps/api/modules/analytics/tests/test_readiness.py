"""
Tests for readiness computation engine (gates, components, levers, confidence).
"""

import uuid

from modules.analytics.domain.readiness import compute_readiness


def test_readiness_cold_start_none():
    res = compute_readiness(
        total_graded=0,
        distinct_days=0,
        days_since_last_answer=0,
        chapter_evidence=[],
        total_chapters_count=10,
    )
    assert res.state == "none"
    assert res.score is None
    assert len(res.missing_gates) > 0


def test_readiness_sparse_gate():
    res = compute_readiness(
        total_graded=15,  # under 30
        distinct_days=2,  # under 3
        days_since_last_answer=1,
        chapter_evidence=[
            {"chapter_id": uuid.uuid4(), "chapter_name": "Tax Basics", "answered": 15, "credit_sum": 10.0, "days_ago": 1, "weight": 10.0}
        ],
        total_chapters_count=10,
    )
    assert res.state == "sparse"
    assert res.score is None


def test_readiness_early_gate_weight_share():
    # 35 answers over 3 days, but all in 1 small chapter representing 5% weight
    cid = uuid.uuid4()
    res = compute_readiness(
        total_graded=35,
        distinct_days=3,
        days_since_last_answer=1,
        chapter_evidence=[
            {"chapter_id": cid, "chapter_name": "Definitions", "answered": 35, "credit_sum": 28.0, "days_ago": 1, "weight": 5.0},
            {"chapter_id": uuid.uuid4(), "chapter_name": "Major Head", "answered": 0, "credit_sum": 0.0, "days_ago": 0, "weight": 95.0},
        ],
        total_chapters_count=10,
    )
    assert res.state == "early"
    assert res.score is None


def test_readiness_ready_score_and_levers():
    # Meets all gates
    c1, c2, c3 = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    res = compute_readiness(
        total_graded=60,
        distinct_days=5,
        days_since_last_answer=2,
        chapter_evidence=[
            {"chapter_id": c1, "chapter_name": "Salaries", "answered": 25, "credit_sum": 20.0, "days_ago": 2, "weight": 20.0},
            {"chapter_id": c2, "chapter_name": "House Property", "answered": 20, "credit_sum": 16.0, "days_ago": 3, "weight": 15.0},
            {"chapter_id": c3, "chapter_name": "GST Returns", "answered": 15, "credit_sum": 12.0, "days_ago": 4, "weight": 15.0},
        ],
        total_chapters_count=6,
        coverage_fraction=0.60,
        retention_fraction=0.80,
        speed_fraction=0.90,
    )
    assert res.state == "ready"
    assert res.score is not None
    assert 50.0 <= res.score <= 100.0
    assert res.confidence in ("high", "medium", "low")
    assert res.label in ("Solid", "Strong", "Getting there")
    assert len(res.components) == 5


def test_readiness_stale():
    c1 = uuid.uuid4()
    res = compute_readiness(
        total_graded=40,
        distinct_days=4,
        days_since_last_answer=35,  # > 21 days
        chapter_evidence=[
            {"chapter_id": c1, "chapter_name": "Salaries", "answered": 40, "credit_sum": 30.0, "days_ago": 35, "weight": 50.0}
        ],
        total_chapters_count=2,
    )
    assert res.state == "stale"
    assert res.score is not None
