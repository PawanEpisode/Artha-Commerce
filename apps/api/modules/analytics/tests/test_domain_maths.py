"""
Tests for domain mathematical calculations (Wilson score, decay, shrinkage, speed).
"""

from decimal import Decimal

from modules.analytics.domain.diagnosis import TimeVsScoreClass, diagnose_time_vs_score
from modules.analytics.domain.maths import (
    beta_shrinkage,
    compute_pace_ratio,
    compute_time_decay_weight,
    wilson_score_interval,
)
from modules.analytics.domain.speed import SpeedFlag, categorize_speed


def test_wilson_score_empty():
    center, lower, upper = wilson_score_interval(0, 0)
    assert (center, lower, upper) == (0.0, 0.0, 0.0)


def test_wilson_score_bounds():
    center, lower, upper = wilson_score_interval(10, 10)
    assert 0.0 < lower < center <= 1.0
    assert upper == 1.0

    center, lower, upper = wilson_score_interval(5, 10)
    assert 0.2 < lower < center < upper < 0.8
    assert round(center, 2) == 0.50


def test_time_decay_weights():
    # 0 days ago -> 1.0
    assert compute_time_decay_weight(0, half_life_days=45) == 1.0

    # 45 days ago -> 0.5
    assert round(compute_time_decay_weight(45, half_life_days=45), 2) == 0.50

    # 90 days ago -> 0.25
    assert round(compute_time_decay_weight(90, half_life_days=45), 2) == 0.25

    # 181 days ago (past lookback_factor=4 x 45 = 180) -> 0.0
    assert compute_time_decay_weight(181, half_life_days=45, lookback_factor=4) == 0.0

    # Exam mode boost (1.25x)
    w_exam = compute_time_decay_weight(0, mode="exam", mode_weight_exam=Decimal("1.25"))
    assert w_exam == 1.25

    # Repeat penalty (0.50x)
    w_repeat = compute_time_decay_weight(0, is_repeat=True, repeat_weight=Decimal("0.50"))
    assert w_repeat == 0.50


def test_beta_shrinkage():
    # 0 observations -> prior mean
    assert beta_shrinkage(0, 0, prior_mean=0.50, prior_strength=4.0) == 0.50

    # Sparse observation: 1 of 1 (100%) shrunk toward 50%
    # (4 * 0.5 + 1) / (4 + 1) = 3 / 5 = 0.60
    assert round(beta_shrinkage(1, 1, prior_mean=0.50, prior_strength=4.0), 2) == 0.60

    # Large evidence: 90 of 100 correct -> dominates prior
    # (4 * 0.5 + 90) / (4 + 100) = 92 / 104 = 0.8846
    assert round(beta_shrinkage(90, 100, prior_mean=0.50, prior_strength=4.0), 2) == 0.88


def test_pace_and_speed_categorization():
    assert compute_pace_ratio(0, 60000) is None
    assert compute_pace_ratio(60000, 60000) == 1.0

    # Fast and wrong: took 30s for a 60s question (<0.85) and wrong
    ratio = compute_pace_ratio(30000, 60000)
    assert categorize_speed(ratio, is_correct=False) == SpeedFlag.FAST_AND_WRONG

    # Slow and right: took 90s for a 60s question (>1.15) and right
    ratio_slow = compute_pace_ratio(90000, 60000)
    assert categorize_speed(ratio_slow, is_correct=True) == SpeedFlag.SLOW_AND_RIGHT

    # On target: took 60s for a 60s question
    assert categorize_speed(1.0, is_correct=True) == SpeedFlag.ON_TARGET


def test_time_vs_score_diagnosis():
    # High time, low score
    assert diagnose_time_vs_score(
        study_seconds=3600,
        accuracy=0.45,
        time_threshold_seconds=1800,
        accuracy_threshold=0.70,
        answered_count=10,
    ) == TimeVsScoreClass.HIGH_TIME_LOW_SCORE

    # Low time, high score
    assert diagnose_time_vs_score(
        study_seconds=600,
        accuracy=0.85,
        time_threshold_seconds=1800,
        accuracy_threshold=0.70,
        answered_count=10,
    ) == TimeVsScoreClass.LOW_TIME_HIGH_SCORE
