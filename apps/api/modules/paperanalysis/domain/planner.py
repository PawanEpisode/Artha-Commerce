"""
Pure greedy planner with 2-approximation safeguard for F-11.
Reference: PRD 6.2 and ERD 3.5.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from .params import DEFAULT_PARAMS
from .types import PlanInputs, PlanPreview, PlanPreviewItem


@dataclass(frozen=True)
class PlannerChapterCandidate:
    chapter_id: UUID
    chapter_key: str
    subject_key: str
    name: str
    sort_order: int
    expected_marks: float  # E
    coverage_fraction: float  # 0 to 1
    accuracy: float  # 0 to 1
    base_minutes: int
    effort_basis: str
    confidence: str


@dataclass
class PlannerPaceContext:
    pace: float = 1.0
    pace_basis: str = "at standard pace"


def compute_personal_pace(
    finished_chapters_tracked_minutes: list[tuple[int, int]],  # (tracked_min, estimate_min)
    params: dict[str, Any] | None = None,
) -> PlannerPaceContext:
    """
    Computes shrunk student pace from tracked study history.
    """
    p = params or DEFAULT_PARAMS
    min_tracked = int(p.get("pace_min_tracked_minutes", 30))
    pace_prior_n = float(p.get("pace_prior_n", 3))
    clamp_lo, clamp_hi = p.get("pace_clamp", [0.6, 1.8])

    valid = [
        tracked / max(1, est)
        for tracked, est in finished_chapters_tracked_minutes
        if tracked >= min_tracked and est > 0
    ]
    n = len(valid)
    if n == 0:
        return PlannerPaceContext(pace=1.0, pace_basis="at standard pace")

    # Median ratio
    valid.sort()
    mid = n // 2
    median_ratio = valid[mid] if (n % 2 == 1) else (valid[mid - 1] + valid[mid]) / 2.0

    raw_pace = (n * median_ratio + pace_prior_n * 1.0) / (n + pace_prior_n)
    clamped_pace = max(clamp_lo, min(clamp_hi, raw_pace))
    return PlannerPaceContext(
        pace=round(clamped_pace, 2),
        pace_basis="at your own pace",
    )


def plan_n_days(
    inputs: PlanInputs,
    candidates: list[PlannerChapterCandidate],
    pace_ctx: PlannerPaceContext | None = None,
    params: dict[str, Any] | None = None,
) -> PlanPreview:
    """
    Executes greedy knapsack selection by expected marks per hour with 2-approximation safeguard,
    skim mode for fractional leftover, and optional subject balancing.
    """
    p = params or DEFAULT_PARAMS
    buffer = float(p.get("budget_buffer", 0.10))
    target_ready = float(p.get("target_ready", 0.75))
    skim_hours_factor = float(p.get("skim_hours_factor", 0.5))
    skim_gain_factor = float(p.get("skim_gain_factor", 0.6))
    pace = pace_ctx.pace if pace_ctx else 1.0

    # Total budget hours with 10% buffer
    raw_budget_hours = inputs.days * inputs.hours_per_day
    budget_hours = round(raw_budget_hours * (1.0 - buffer), 2)

    # Filter eligible candidates: in selected subjects, gain > 0, confidence not insufficient
    eligible: list[dict[str, Any]] = []
    total_historical_E = sum(c.expected_marks for c in candidates)

    for c in candidates:
        if c.subject_key not in inputs.subject_keys:
            continue
        if c.confidence == "insufficient":
            continue

        ready_now = c.coverage_fraction * (0.5 + 0.5 * c.accuracy)
        gap = max(0.0, target_ready - ready_now)
        gain = c.expected_marks * gap
        if gain <= 0.001:
            continue

        r = gap / target_ready
        hours = max(0.2, (c.base_minutes * r * pace) / 60.0)
        mph = gain / hours

        eligible.append({
            "cand": c,
            "gain": gain,
            "hours": hours,
            "mph": mph,
            "mode": "full",
        })

    # Sort candidates by mph desc, then expected_marks desc, sort_order, chapter_id
    eligible.sort(
        key=lambda item: (
            -item["mph"],
            -item["cand"].expected_marks,
            item["cand"].sort_order,
            str(item["cand"].chapter_id),
        )
    )

    # Greedy packing
    hours_used = 0.0
    chosen: list[dict[str, Any]] = []
    remaining_candidates: list[dict[str, Any]] = []

    for item in eligible:
        if hours_used + item["hours"] <= budget_hours:
            chosen.append(item)
            hours_used += item["hours"]
        else:
            remaining_candidates.append(item)

    # 2-approximation safeguard: compare greedy total gain with the best single item that fits
    greedy_gain = sum(it["gain"] for it in chosen)
    best_single = None
    best_single_gain = -1.0

    for item in eligible:
        if item["hours"] <= budget_hours and item["gain"] > best_single_gain:
            best_single_gain = item["gain"]
            best_single = item

    if best_single is not None and best_single_gain > greedy_gain:
        chosen = [best_single]
        hours_used = best_single["hours"]
        remaining_candidates = [it for it in eligible if it["cand"].chapter_id != best_single["cand"].chapter_id]

    # Skim mode (key points only) for the next candidate if at least half of its hours fit
    leftover = budget_hours - hours_used
    if remaining_candidates:
        next_cand = remaining_candidates[0]
        skim_hours = next_cand["hours"] * skim_hours_factor
        if leftover >= skim_hours:
            skim_gain = next_cand["gain"] * skim_gain_factor
            chosen.append({
                "cand": next_cand["cand"],
                "gain": skim_gain,
                "hours": skim_hours,
                "mph": skim_gain / max(0.1, skim_hours),
                "mode": "key_points",
            })
            hours_used += skim_hours

    # Subject balancing if requested
    if inputs.balance_subjects and len(inputs.subject_keys) > 1:
        # Check if any subject has 0 hours
        represented = {it["cand"].subject_key for it in chosen}
        for skey in inputs.subject_keys:
            if skey not in represented:
                # Find best candidate for missing subject
                for item in eligible:
                    if item["cand"].subject_key == skey and item["hours"] <= budget_hours:
                        # Swap lowest-mph item if needed to include this subject
                        if chosen and (hours_used - chosen[-1]["hours"] + item["hours"] <= budget_hours):
                            hours_used = hours_used - chosen[-1]["hours"] + item["hours"]
                            chosen.pop()
                            chosen.append(item)
                            represented.add(skey)
                            break

    # Build PlanPreview items
    preview_items: list[PlanPreviewItem] = []
    chosen_ids = set()
    chosen_E_sum = 0.0

    for it in chosen:
        cand = it["cand"]
        chosen_ids.add(cand.chapter_id)
        chosen_E_sum += cand.expected_marks
        preview_items.append(
            PlanPreviewItem(
                chapter_id=cand.chapter_id,
                chapter_key=cand.chapter_key,
                subject_key=cand.subject_key,
                minutes=int(round(it["hours"] * 60)),
                mode=it["mode"],
                expected_gain=round(it["gain"], 1),
                mph=round(it["mph"], 1),
                effort_basis=cand.effort_basis,
            )
        )

    left_out_candidates = [c for c in candidates if c.chapter_id not in chosen_ids and c.subject_key in inputs.subject_keys]
    left_out_E_sum = sum(c.expected_marks for c in left_out_candidates)

    covered_share = round(chosen_E_sum / total_historical_E, 2) if total_historical_E > 0 else 0.0
    left_out_share = round(left_out_E_sum / total_historical_E, 2) if total_historical_E > 0 else 0.0

    return PlanPreview(
        v=1,
        inputs={
            "days": inputs.days,
            "hours_per_day": inputs.hours_per_day,
            "subject_keys": list(inputs.subject_keys),
            "balance_subjects": inputs.balance_subjects,
        },
        budget_hours=round(budget_hours, 1),
        hours_used=round(hours_used, 1),
        items=preview_items,
        covered_share=covered_share,
        left_out={
            "chapters_n": len(left_out_candidates),
            "share": left_out_share,
        },
        snapshot_id=None,
    )
