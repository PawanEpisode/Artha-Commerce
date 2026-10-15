"""
Negative-marking insight calculation (F-05 ERD 3.5).
Analyzes answers with confidence ratings to evaluate whether guessing paid off,
break-even accuracy, penalties applied, and sure-but-wrong concepts.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class AnswerInsightInput:
    result: str  # "correct", "incorrect", "partial", "skipped"
    confidence: int | None  # 1: sure, 2: unsure, 3: guess, None
    marks_max: Decimal
    negative_max: Decimal
    marks_awarded: Decimal
    negative_applied: Decimal


@dataclass(frozen=True)
class ConfidenceBandStats:
    count: int
    correct_count: int
    accuracy_pct: float
    net_marks: Decimal
    paying_off: bool | None  # None if no break-even defined


@dataclass(frozen=True)
class NegativeInsightReport:
    total_penalties: Decimal
    penalised_count: int
    break_even_pct: float | None
    sure_but_wrong_count: int
    sure: ConfidenceBandStats
    unsure: ConfidenceBandStats
    guess: ConfidenceBandStats


def compute_negative_insight(answers: Sequence[AnswerInsightInput]) -> NegativeInsightReport:
    """Computes negative marking review insights from graded answers."""
    total_penalties = Decimal("0")
    penalised_count = 0
    sure_but_wrong = 0

    # Break-even calculation based on the first item with non-zero negative
    sample_neg = Decimal("0")
    sample_pos = Decimal("0")
    for a in answers:
        if a.negative_max > 0 and sample_neg == 0:
            sample_neg = a.negative_max
            sample_pos = a.marks_max

    break_even_pct: float | None = None
    if sample_neg > 0 and (sample_pos + sample_neg) > 0:
        break_even_pct = round(float(sample_neg / (sample_pos + sample_neg)) * 100.0, 1)

    bands = {
        1: {"n": 0, "correct": 0, "net": Decimal("0")},
        2: {"n": 0, "correct": 0, "net": Decimal("0")},
        3: {"n": 0, "correct": 0, "net": Decimal("0")},
    }

    for a in answers:
        if a.negative_applied > 0:
            total_penalties += a.negative_applied
            penalised_count += 1

        conf = a.confidence
        if conf in bands:
            b = bands[conf]
            b["n"] += 1
            if a.result == "correct":
                b["correct"] += 1
            b["net"] += a.marks_awarded

        if conf == 1 and a.result in ("incorrect", "partial"):
            sure_but_wrong += 1

    def build_band_stats(conf_id: int) -> ConfidenceBandStats:
        b = bands[conf_id]
        cnt = b["n"]
        corr = b["correct"]
        acc = round((corr / cnt) * 100.0, 1) if cnt > 0 else 0.0
        paying_off = (acc > break_even_pct) if (break_even_pct is not None and cnt > 0) else None
        return ConfidenceBandStats(
            count=cnt,
            correct_count=corr,
            accuracy_pct=acc,
            net_marks=b["net"],
            paying_off=paying_off,
        )

    return NegativeInsightReport(
        total_penalties=total_penalties,
        penalised_count=penalised_count,
        break_even_pct=break_even_pct,
        sure_but_wrong_count=sure_but_wrong,
        sure=build_band_stats(1),
        unsure=build_band_stats(2),
        guess=build_band_stats(3),
    )
