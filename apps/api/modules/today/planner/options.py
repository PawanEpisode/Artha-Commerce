"""
Options for a plan that does not fit (FR-F13-49): more daily time, skim the low-weight chapters, or sit the next attempt.

Nothing here changes a plan. `compute_options` lists what each choice would do, with the numbers, and `apply_option` returns the
changed inputs for the choice the student made, so a test (and the service) can check that a feasible option really closes the gap.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace
from datetime import date
from fractions import Fraction
from typing import Any

from . import capacity as cap
from . import constants as pc


def more_time_option(params: cap.PlanParams, remaining: int) -> dict[str, Any] | None:
    """The daily minutes that make the capacity reach the remaining work. None when no reading days are left (nothing helps)."""
    days = cap.learn_days(params)
    if days == 0:
        return None
    required = cap.ceil_div(remaining * cap.PERCENT_PAIR, days * params.utilisation_pct * params.learn_share_pct)
    return {
        "option": "more_time",
        "daily_minutes": required,
        "extra_minutes": required - params.daily_minutes,
        "feasible": required <= pc.DAILY_MINUTES_MAX,
    }


def skim_candidates(chapters: Sequence[cap.ChapterInput]) -> list[tuple[Fraction, str, int]]:
    """Chapters that can be skimmed, lowest marks per minute first, as `(marks per minute, key, minutes saved)`.

    Ties are broken by key. A chapter that is already skimmed, read, excluded or has a single minute left saves nothing and is left out.
    """
    rows = []
    for chapter in chapters:
        left = cap.chapter_remaining(chapter)
        saved = left - cap.ceil_div(left * pc.SKIM_FACTOR_PCT, 100)
        if chapter.skim or saved <= 0:
            continue
        weight = Fraction(str(max(0.0, chapter.marks_weight)))
        rows.append((weight / left, chapter.key, saved))
    rows.sort(key=lambda row: (row[0], row[1]))
    return rows


def skim_pick(chapters: Sequence[cap.ChapterInput], shortfall: int) -> tuple[list[str], int]:
    """The chapters to skim, in order, until the savings cover the shortfall, and the minutes they save."""
    picked: list[str] = []
    saved = 0
    for _, key, minutes in skim_candidates(chapters):
        if saved >= shortfall:
            break
        picked.append(key)
        saved += minutes
    return picked, saved


def skim_option(chapters: Sequence[cap.ChapterInput], shortfall: int) -> dict[str, Any]:
    """Skim chapters in order until the savings cover the shortfall; `feasible` is false when skimming everything still falls short.

    The list of keys is cut for storage (`chapter_count` is exact); `apply_option` works the full list out again.
    """
    picked, saved = skim_pick(chapters, shortfall)
    return {
        "option": "skim_low_weight",
        "chapter_count": len(picked),
        "chapters": picked[: pc.SUMMARY_MAX_SKIM_CHAPTERS],
        "saved_minutes": saved,
        "feasible": saved >= shortfall,
    }


def next_attempt_option(
    params: cap.PlanParams, chapters: Sequence[cap.ChapterInput], next_exam_date: date | None
) -> dict[str, Any]:
    """Sit the next open attempt (F-02 supplies the date). Without a later date the option is shown as not feasible."""
    if next_exam_date is None or next_exam_date <= params.exam_date:
        return {"option": "next_attempt", "exam_date": None, "shortfall_minutes": None, "feasible": False}
    later = cap.compute_capacity(params.but(exam_date=next_exam_date, reading_deadline=None), chapters)
    return {
        "option": "next_attempt",
        "exam_date": next_exam_date.isoformat(),
        "shortfall_minutes": later.shortfall_minutes,
        "feasible": later.shortfall_minutes == 0,
    }


def compute_options(
    params: cap.PlanParams,
    chapters: Sequence[cap.ChapterInput],
    next_exam_date: date | None = None,
) -> list[dict[str, Any]]:
    """The options for a plan with a shortfall (none for a plan that fits). `more_time` is left out when no reading days remain."""
    current = cap.compute_capacity(params, chapters)
    if current.shortfall_minutes == 0:
        return []
    options = [
        more_time_option(params, current.remaining_minutes),
        skim_option(chapters, current.shortfall_minutes),
        next_attempt_option(params, chapters, next_exam_date),
    ]
    return [option for option in options if option is not None]


def apply_option(
    params: cap.PlanParams, chapters: Sequence[cap.ChapterInput], option: dict[str, Any]
) -> tuple[cap.PlanParams, list[cap.ChapterInput]]:
    """The inputs after the student chose `option` (a dict from `compute_options`). `none` and unknown choices change nothing."""
    kind = option.get("option")
    if kind == "more_time":
        return params.but(daily_minutes=option["daily_minutes"]), list(chapters)
    if kind == "next_attempt" and option.get("exam_date"):
        return params.but(exam_date=date.fromisoformat(option["exam_date"]), reading_deadline=None), list(chapters)
    if kind == "skim_low_weight":
        picked, _ = skim_pick(chapters, cap.compute_capacity(params, chapters).shortfall_minutes)
        skimmed = set(picked)
        return params, [replace(ch, skim=True) if ch.key in skimmed else ch for ch in chapters]
    return params, list(chapters)
