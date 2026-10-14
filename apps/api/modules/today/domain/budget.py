"""Time budget, focus papers and comeback mode (PRD 5.4 step 3, 5.5). Integer arithmetic, half up, so Python and TypeScript agree."""

from __future__ import annotations

from collections.abc import Sequence

from .constants import (
    AUTO_BUDGET_MAX,
    AUTO_BUDGET_MIN,
    AUTO_BUDGET_SHARE_PCT,
    BUDGET_MAX,
    BUDGET_MIN,
    COMEBACK_BUDGET_PCT,
    COMEBACK_MAX_TASKS,
    COMEBACK_MISSED_DAYS,
    DEFAULT_BUDGET_MINUTES,
    FOCUS_MINUTES_PER_PAPER,
    FOCUS_PAPERS_MAX,
    FOCUS_PAPERS_MIN,
    FOCUS_PAPERS_SETTING_MAX,
    MAX_TASKS,
    SETTING_MINUTES_MAX,
    SETTING_MINUTES_MIN,
)


def _clamp(value: int, low: int, high: int) -> int:
    return max(low, min(high, value))


def auto_budget(daily_minutes: int | None) -> int:
    """
    `clamp(round5(0.35 * daily_minutes), 30, 120)`. With unknown daily hours the budget is `DEFAULT_BUDGET_MINUTES` (60), not the
    formula applied to 60: the first plan promises "about 1 h" (PRD 7.3) and a 30 minute plan for a student we know nothing about
    would be the thin one. Decision recorded in `docs/F-13-BUILD-WAVES.md`.
    """
    if daily_minutes is None or daily_minutes <= 0:
        return DEFAULT_BUDGET_MINUTES
    rounded_to_5 = ((AUTO_BUDGET_SHARE_PCT * daily_minutes + 250) // 500) * 5
    return _clamp(rounded_to_5, AUTO_BUDGET_MIN, AUTO_BUDGET_MAX)


def budget_for(*, setting_minutes: int | None, daily_minutes: int | None) -> tuple[int, str]:
    """The budget `B` and where it came from (`setting` when the student chose minutes, else `auto`)."""
    if setting_minutes is not None:
        return _clamp(setting_minutes, SETTING_MINUTES_MIN, SETTING_MINUTES_MAX), "setting"
    return auto_budget(daily_minutes), "auto"


def comeback_budget(budget: int) -> int:
    """Budget times 0.6, half up, never under the database floor."""
    return max(BUDGET_MIN, min(BUDGET_MAX, (budget * COMEBACK_BUDGET_PCT + 50) // 100))


def focus_papers(budget: int, setting: int | None = None) -> int:
    """`clamp(round(B / 40), 1, 3)` (half up); the student's own setting (1 to 4) wins."""
    if setting is not None:
        return _clamp(setting, FOCUS_PAPERS_MIN, FOCUS_PAPERS_SETTING_MAX)
    half_up = (2 * budget + FOCUS_MINUTES_PER_PAPER) // (2 * FOCUS_MINUTES_PER_PAPER)
    return _clamp(half_up, FOCUS_PAPERS_MIN, FOCUS_PAPERS_MAX)


def is_comeback(recent_days_active: Sequence[bool], *, had_activity_before: bool) -> bool:
    """
    True when each of the last `COMEBACK_MISSED_DAYS` complete local days (most recent first) has no tracked time and no done task
    (`False` entries), for a student who has studied before. A brand new student is not "coming back", and fewer than three days
    of history cannot prove three missed days.
    """
    if not had_activity_before or len(recent_days_active) < COMEBACK_MISSED_DAYS:
        return False
    return not any(recent_days_active[:COMEBACK_MISSED_DAYS])


def task_cap(comeback: bool) -> int:
    return COMEBACK_MAX_TASKS if comeback else MAX_TASKS
