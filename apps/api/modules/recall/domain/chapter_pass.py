"""
The chapter recall pass (PRD FR-F15-64), pure. A chapter's set is its active mandatory and important cards. The chapter is
"passed" when the set has at least 5 cards and at least 80 percent of them were reviewed Hard or better inside the last 7 days.
Nothing here reads the clock or the database: the caller counts and passes `now`.

Decisions (the PRD leaves these open; `vectors/chapter_pass_cases.json` pins them):
- "Within the last 7 days" means younger than 7 x 24 hours: a review exactly 7 days old has left the window.
- 80 percent is integer arithmetic (`ok * 5 >= size * 4`), so 79 of 100 fails and 80 of 100 passes with no rounding doubt.
- "Once per chapter per 7 days" is a rolling cool-down from the last pass that was announced (the PRD wording), not the ISO
  week the ERD sketched: a pass announced on a Sunday would otherwise allow another on the Monday. A pass exactly 7 days
  old no longer blocks a new one.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

MIN_SET = 5  # a set smaller than this can never be passed: five cards is not a chapter
PASS_PERCENT = 80
WINDOW = timedelta(days=7)  # reviews count while younger than this
COOLDOWN = timedelta(days=7)  # at most one announced pass per chapter in this time
MIN_IMPORTANCE = 1  # important (1) and mandatory (2); bullets are not part of the set


@dataclass(frozen=True)
class PassResult:
    set_size: int
    reviewed_ok: int  # cards of the set with a Hard or better review inside the window
    coverage_of_set: float  # reviewed_ok / set_size, 4 places (0.0 for an empty set)
    eligible: bool  # the set is large enough to be passed at all
    passed: bool


def in_window(reviewed_at: datetime, now: datetime) -> bool:
    """True while the review is younger than 7 days (and not from the future)."""
    return now - WINDOW < reviewed_at <= now


def evaluate(set_size: int, reviewed_ok: int) -> PassResult:
    """The pass rule on two counts. `reviewed_ok` is clamped to the set, so a stray extra count cannot pass a chapter."""
    size = max(int(set_size), 0)
    ok = min(max(int(reviewed_ok), 0), size)
    eligible = size >= MIN_SET
    return PassResult(
        set_size=size,
        reviewed_ok=ok,
        coverage_of_set=round(ok / size, 4) if size else 0.0,
        eligible=eligible,
        passed=eligible and ok * 100 >= PASS_PERCENT * size,
    )


def cooldown_over(last_pass_at: datetime | None, now: datetime) -> bool:
    """A new pass may be announced when none was announced in the last 7 days (a pass exactly 7 days old is over)."""
    return last_pass_at is None or now - last_pass_at >= COOLDOWN
