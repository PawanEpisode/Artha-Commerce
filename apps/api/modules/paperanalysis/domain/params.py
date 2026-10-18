"""
Scoring parameters, validation and defaults for engine ps-1.
Reference: PRD 6.1 and ERD 3.5.
"""

from __future__ import annotations

from typing import Any

ENGINE_VERSION = "ps-1"
PARAMS_SCHEMA_VERSION = 1

DEFAULT_PARAMS: dict[str, Any] = {
    "window_max": 10,
    "trend_min_papers": 5,
    "recency_lambda": 0.85,
    "kind_weight": {
        "exam": 1.0,
        "mtp": 0.4,
        "rtp": 0.3,
        "sample": 0.3,
    },
    "carry_weight": 0.7,
    "shrink_k": 2.0,
    "acc_prior_strength": 5.0,
    "weights_far": {
        "H": 0.40,
        "F": 0.15,
        "T": 0.05,
        "W": 0.20,
        "G": 0.20,
    },
    "weights_near": {
        "H": 0.50,
        "F": 0.15,
        "T": 0.05,
        "W": 0.10,
        "G": 0.20,
    },
    "urgency_ref_days": 120,
    "tier_core_share": 0.50,
    "tier_next_share": 0.80,
    "target_ready": 0.75,
    "skim_hours_factor": 0.5,
    "skim_gain_factor": 0.6,
    "budget_buffer": 0.10,
    "min_papers_for_stats": 3,
    "min_papers_to_rank": 4,
    "min_exam_papers_for_core": 2,
    "pace_clamp": [0.6, 1.8],
    "pace_prior_n": 3,
    "pace_min_tracked_minutes": 30,
    "fallback_minutes_per_topic": 40,
    "fallback_minutes_default": 240,
    "backtest_k": 0.30,
    "min_backtest_lift": 1.15,
    "default_days_left": 90,
    "today_max_tasks": 2,
}


def validate_params(params: dict[str, Any]) -> None:
    """Validates parameters dictionary against the schema."""
    required_keys = [
        "window_max", "trend_min_papers", "recency_lambda", "kind_weight",
        "carry_weight", "shrink_k", "acc_prior_strength", "weights_far",
        "weights_near", "urgency_ref_days", "tier_core_share", "tier_next_share",
        "target_ready", "budget_buffer", "min_papers_to_rank",
    ]
    for k in required_keys:
        if k not in params:
            raise ValueError(f"Missing required parameter: {k}")

    # Check lambda
    rec_lambda = params["recency_lambda"]
    if not (0.0 < rec_lambda <= 1.0):
        raise ValueError("recency_lambda must be in (0, 1]")

    # Check weights_far and weights_near sum to 1.0
    for name in ("weights_far", "weights_near"):
        w_dict = params[name]
        for comp in ("H", "F", "T", "W", "G"):
            if comp not in w_dict:
                raise ValueError(f"{name} missing component {comp}")
            if w_dict[comp] < 0:
                raise ValueError(f"{name}[{comp}] must be non-negative")
        total = sum(w_dict.values())
        if abs(total - 1.0) > 0.001:
            raise ValueError(f"{name} must sum to 1.0 (got {total})")

    # Check non-negative scalars
    for k in ("carry_weight", "shrink_k", "acc_prior_strength", "urgency_ref_days", "budget_buffer"):
        if params[k] < 0:
            raise ValueError(f"{k} must be non-negative")
