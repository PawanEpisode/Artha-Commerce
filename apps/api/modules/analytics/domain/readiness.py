"""
Pure readiness calculation engine (F-10 PRD 4.9, FR-F10-30..38, ERD 2.6, 3.6).
Computes readiness score, confidence band, gates, component breakdown, and actionable levers.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from .limits import (
    BAND_FLOOR,
    BAND_HIGH_CUTOFF,
    BAND_MAX_HALFWIDTH,
    BAND_MEDIUM_CUTOFF,
    BAND_MISSING_ADD,
    DEFAULT_HALF_LIFE_DAYS,
    DEFAULT_LOOKBACK_FACTOR,
    DEFAULT_WEIGHT_ACCURACY,
    DEFAULT_WEIGHT_BREADTH,
    DEFAULT_WEIGHT_COVERAGE,
    DEFAULT_WEIGHT_RETENTION,
    DEFAULT_WEIGHT_SPEED,
    LABEL_GETTING_THERE,
    LABEL_SOLID,
    LABEL_STRONG,
    MIN_ANSWERS_CHAPTER,
    MIN_ANSWERS_SUBJECT,
    MIN_DAYS_SUBJECT,
    MIN_WEIGHT_SHARE,
    RECENT_WINDOW_DAYS,
    STALE_AFTER_DAYS,
)
from .maths import compute_time_decay_weight


@dataclass
class ReadinessComponent:
    key: str
    label: str
    value: float
    weight: float
    points: float
    available: bool


@dataclass
class ReadinessLever:
    action: str
    impact_points: float
    target_type: str
    target_id: str | None = None
    target_name: str | None = None


@dataclass
class ReadinessResult:
    state: str                 # 'none', 'sparse', 'early', 'ready', 'stale'
    score: float | None        # 0.0 to 100.0, rounded to 1 decimal
    half_width: float | None   # confidence band margin
    confidence: str | None     # 'high', 'medium', 'low'
    label: str | None          # 'Getting there', 'Solid', 'Strong'
    components: list[ReadinessComponent]
    levers: list[ReadinessLever]
    missing_gates: list[str]
    inputs: dict[str, Any] = field(default_factory=dict)


def compute_readiness(
    *,
    total_graded: int,
    distinct_days: int,
    days_since_last_answer: int,
    chapter_evidence: list[dict[str, Any]],  # [{chapter_id, chapter_name, answered, credit_sum, days_ago, weight}]
    total_chapters_count: int,
    coverage_fraction: float | None = None,
    retention_fraction: float | None = None,
    speed_fraction: float | None = None,
    weights: dict[str, Decimal] | None = None,
) -> ReadinessResult:
    """
    Pure readiness calculation.
    Evaluates gates, computes components, assesses confidence band, and generates levers.
    """
    w_acc = float(weights.get("w_accuracy", DEFAULT_WEIGHT_ACCURACY) if weights else DEFAULT_WEIGHT_ACCURACY)
    w_brd = float(weights.get("w_breadth", DEFAULT_WEIGHT_BREADTH) if weights else DEFAULT_WEIGHT_BREADTH)
    w_cov = float(weights.get("w_coverage", DEFAULT_WEIGHT_COVERAGE) if weights else DEFAULT_WEIGHT_COVERAGE)
    w_ret = float(weights.get("w_retention", DEFAULT_WEIGHT_RETENTION) if weights else DEFAULT_WEIGHT_RETENTION)
    w_spd = float(weights.get("w_speed", DEFAULT_WEIGHT_SPEED) if weights else DEFAULT_WEIGHT_SPEED)

    # 1. Evaluate Gates
    missing_gates: list[str] = []
    if total_graded == 0:
        return ReadinessResult(
            state="none",
            score=None,
            half_width=None,
            confidence=None,
            label=None,
            components=[],
            levers=[],
            missing_gates=["Answer at least 30 practice questions to unlock readiness."],
            inputs={"total_graded": 0},
        )

    if total_graded < MIN_ANSWERS_SUBJECT:
        missing_gates.append(f"Needs {MIN_ANSWERS_SUBJECT - total_graded} more practice questions.")

    if distinct_days < MIN_DAYS_SUBJECT:
        missing_gates.append(f"Needs practice across {MIN_DAYS_SUBJECT - distinct_days} more study day(s).")

    # Chapter breadth and weight share
    chapters_ready = 0
    total_weight_available = sum(float(c.get("weight", 1.0)) for c in chapter_evidence) or 1.0
    covered_weight = 0.0

    for c in chapter_evidence:
        if c.get("answered", 0) >= MIN_ANSWERS_CHAPTER:
            chapters_ready += 1
            covered_weight += float(c.get("weight", 1.0))

    weight_share = covered_weight / total_weight_available if total_weight_available > 0 else 0.0

    if weight_share < float(MIN_WEIGHT_SHARE):
        missing_gates.append(f"Cover chapters representing at least {int(float(MIN_WEIGHT_SHARE)*100)}% of the syllabus.")

    is_stale = days_since_last_answer > STALE_AFTER_DAYS
    is_early = bool(missing_gates)

    # State determination
    if total_graded < MIN_ANSWERS_SUBJECT or distinct_days < MIN_DAYS_SUBJECT:
        state = "sparse"
    elif is_early:
        state = "early"
    elif is_stale:
        state = "stale"
    else:
        state = "ready"

    # 2. Component Calculations
    # (a) Accuracy (time-decay weighted)
    weighted_credits = 0.0
    weighted_counts = 0.0
    for c in chapter_evidence:
        days_ago = c.get("days_ago", 0)
        decay = compute_time_decay_weight(days_ago)
        weighted_credits += float(c.get("credit_sum", 0.0)) * decay
        weighted_counts += float(c.get("answered", 0)) * decay

    accuracy_val = (weighted_credits / weighted_counts) if weighted_counts > 0 else 0.50
    accuracy_points = accuracy_val * 100.0 * w_acc

    # (b) Breadth
    breadth_val = (chapters_ready / total_chapters_count) if total_chapters_count > 0 else 0.0
    breadth_points = min(1.0, breadth_val) * 100.0 * w_brd

    # (c) Coverage
    cov_val = coverage_fraction if coverage_fraction is not None else 0.0
    cov_points = min(1.0, max(0.0, cov_val)) * 100.0 * w_cov

    # (d) Retention
    ret_val = retention_fraction if retention_fraction is not None else 0.50
    ret_points = min(1.0, max(0.0, ret_val)) * 100.0 * w_ret

    # (e) Speed
    spd_val = speed_fraction if speed_fraction is not None else 0.80
    spd_points = min(1.0, max(0.0, spd_val)) * 100.0 * w_spd

    raw_score = accuracy_points + breadth_points + cov_points + ret_points + spd_points
    score = round(max(0.0, min(100.0, raw_score)), 1) if state in ("ready", "stale") else None

    # 3. Confidence Band
    # Based on sample size and breadth
    base_spread = 20.0 / math.sqrt(max(1, total_graded))
    penalty = 1.0 + (1.0 - min(1.0, breadth_val)) * 0.5
    half_width_calc = max(float(BAND_FLOOR), base_spread * penalty)
    if is_stale:
        half_width_calc += float(BAND_MISSING_ADD)
    half_width = round(min(float(BAND_MAX_HALFWIDTH), half_width_calc), 1)

    if half_width <= float(BAND_HIGH_CUTOFF):
        confidence = "high"
    elif half_width <= float(BAND_MEDIUM_CUTOFF):
        confidence = "medium"
    else:
        confidence = "low"

    # Label
    label = None
    if score is not None:
        if score >= LABEL_STRONG:
            label = "Strong"
        elif score >= LABEL_SOLID:
            label = "Solid"
        elif score >= LABEL_GETTING_THERE:
            label = "Getting there"
        else:
            label = "Needs work"

    components = [
        ReadinessComponent("accuracy", "Practice Accuracy", round(accuracy_val, 3), w_acc, round(accuracy_points, 1), True),
        ReadinessComponent("breadth", "Syllabus Breadth", round(breadth_val, 3), w_brd, round(breadth_points, 1), True),
        ReadinessComponent("coverage", "Course Coverage", round(cov_val, 3), w_cov, round(cov_points, 1), coverage_fraction is not None),
        ReadinessComponent("retention", "Concept Retention", round(ret_val, 3), w_ret, round(ret_points, 1), retention_fraction is not None),
        ReadinessComponent("speed", "Pace & Timing", round(spd_val, 3), w_spd, round(spd_points, 1), speed_fraction is not None),
    ]

    # 4. Actionable Levers
    levers: list[ReadinessLever] = []
    # Find untouched or low-answer chapters with high weight
    weak_or_untouched = sorted(
        chapter_evidence,
        key=lambda x: (x.get("answered", 0), -float(x.get("weight", 1.0))),
    )

    for c in weak_or_untouched[:3]:
        ans = c.get("answered", 0)
        name = c.get("chapter_name", "Chapter")
        cid = str(c.get("chapter_id", ""))
        if ans < MIN_ANSWERS_CHAPTER:
            needed = MIN_ANSWERS_CHAPTER - ans
            potential_pts = round(float(w_brd * (1.0 / max(1, total_chapters_count)) * 100.0), 1)
            levers.append(
                ReadinessLever(
                    action=f"Practise {needed} questions in {name}",
                    impact_points=max(1.0, potential_pts),
                    target_type="chapter_practice",
                    target_id=cid,
                    target_name=name,
                )
            )

    return ReadinessResult(
        state=state,
        score=score,
        half_width=half_width,
        confidence=confidence,
        label=label,
        components=components,
        levers=levers,
        missing_gates=missing_gates,
        inputs={
            "total_graded": total_graded,
            "distinct_days": distinct_days,
            "chapters_ready": chapters_ready,
            "weight_share": round(weight_share, 2),
            "days_since_last_answer": days_since_last_answer,
        },
    )
