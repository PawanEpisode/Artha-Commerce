"""Reads for the weekly email (X-01.1 W3.5): the week's numbers, and who may be written to. Other modules are read through their selectors."""

from __future__ import annotations

from datetime import date

from modules.coverage import selectors as coverage_selectors
from modules.profiles import selectors as profile_selectors
from modules.tracking import selectors as tracking_selectors

from ..domain.catalogue import Category, is_enabled
from ..domain.enums import Channel
from ..domain.weekly import WeeklyFacts, week_window
from . import preferences as preference_selectors


def weekly_facts(user_id, local_day: date) -> WeeklyFacts:
    """Study time and streak over the seven local days ending `local_day`, plus coverage, revision due and the exam."""
    first, last = week_window(local_day)
    totals = tracking_selectors.day_totals(user_id, first, last)
    streak = tracking_selectors.streak(user_id, last) if totals else 0
    enrollment = coverage_selectors.get_active_enrollment(user_id)
    if enrollment is None:
        return WeeklyFacts(sum(totals.values()), len(totals), streak, None, 0, None)
    rollup = coverage_selectors.overview(enrollment)["level_rollup"]
    exam = coverage_selectors.exam_date_of(enrollment)
    days = (exam - local_day).days if exam else None
    return WeeklyFacts(
        study_seconds=sum(totals.values()),
        active_days=len(totals),
        streak_days=streak,
        coverage_pct=float(rollup.pct_simple) if rollup else 0.0,
        due_for_revision=len(coverage_selectors.due_for_revision(enrollment, local_day)),
        days_to_exam=days if days is not None and days >= 0 else None,
    )


def email_enabled(user_id) -> bool:
    """The student's own choice for the weekly summary by email (default on)."""
    return is_enabled(Category.PROGRESS.value, Channel.EMAIL.value, preference_selectors.overrides(user_id))


def email_address(user_id) -> str:
    return profile_selectors.email_of(user_id)
