"""
Every number of the F-13 PRD section 5.5 in one place, plus the closed enumerations the database checks and the UI depend on.

Mirrored on the web in `modules/today/lib/limits.ts` with a parity test. Nothing here imports Django, so the engine stays a
pure, unit-testable library. Values are defaults to tune in beta; a plan stores `ALGORITHM_VERSION` so an old plan can still be
explained after a constant changes.
"""

from __future__ import annotations

ALGORITHM_VERSION = 1

# ---- enumerations (closed lists: the database has CHECK constraints for them) -----------------------------------------------
GROUPS = ("learn", "revise", "practice", "exam", "news")
SLOTS = (
    "mcq",
    "formula",
    "section",
    "practical",
    "revision",
    "recall",
    "read",
    "amendment",
    "challenge",
    "custom",
    "other",
)
PHASES = ("steady", "build", "consolidate", "sprint", "final", "post_exam")
PLAN_STATUSES = ("draft", "ready", "closed")
BUDGET_SOURCES = ("auto", "setting", "comeback", "feedback")
ORIGINS = ("provider", "user", "planner")
TASK_STATES = ("suggested", "accepted", "done", "skipped", "snoozed", "expired")
COMPLETED_VIA = ("event", "manual")
SKIP_REASONS = ("not_in_attempt", "already_know", "no_time", "other", "swapped")
END_REASONS = ("day_ended", "regenerated", "no_longer_needed")
LITE_MODES = ("auto", "on", "off")

OPEN_STATES = ("suggested", "accepted")
#: States that count toward the day's plan (the ring): everything the student was asked to do and has not moved away.
PLANNED_STATES = ("suggested", "accepted", "done", "skipped")

# ---- composition (PRD 5.4, 5.5) ---------------------------------------------------------------------------------------------
MAX_TASKS = 8
MIN_TASKS = 3
COMEBACK_MAX_TASKS = 5
COMEBACK_BUDGET_PCT = 60
COMEBACK_MISSED_DAYS = 3
COMEBACK_NEWS_WINDOW_DAYS = 14  # in comeback mode only an amendment for an attempt this close stays must-do

FILL_TARGET_PCT = 90  # stop filling when planned minutes reach this share of the budget
HARD_CAP_PCT = 125  # must-do and floor relaxation may stretch the budget to this share, never more

FOCUS_PAPERS_MIN = 1
FOCUS_PAPERS_MAX = 3
FOCUS_PAPERS_SETTING_MAX = 4
FOCUS_MINUTES_PER_PAPER = 40  # F = clamp(round(B / 40), 1, 3)

PER_PAPER_CAP = 4
PER_SLOT_PER_PAPER = 1
GENERAL_POOL_CAP = 2
REVISION_SLOT_CAP = 3  # backlog smoothing: at most three `revision` slot tasks a day
# A paper untouched for this many days (or never touched) is "starved": it gets the need bonus AND takes a focus slot before any
# paper that is not starved. The PRD (5.4 step 3) specifies 4 days and the bonus alone, but the 60-day simulation showed the
# bonus cannot beat normal score variation (a paper stayed out for 10 to 14 days). With hard priority, the longest-waiting paper
# first, the worst case is STARVATION_DAYS + ceil(N / F) - 2 days, which meets the PRD's own bound of ceil(N / F) + 1 only when
# STARVATION_DAYS is 3. See docs/F-13-BUILD-WAVES.md, "Changes to the PRD to approve".
STARVATION_DAYS = 3
STARVATION_BONUS = 150
MUST_DO_BONUS = 300
MISS_PENALTY = 40
MISS_PENALTY_MAX_MISSES = 3
STARTER_MAX_MINUTES = 10

# ---- budget -----------------------------------------------------------------------------------------------------------------
AUTO_BUDGET_SHARE_PCT = 35
AUTO_BUDGET_MIN = 30
AUTO_BUDGET_MAX = 120
DEFAULT_BUDGET_MINUTES = 60  # when the student's daily hours are unknown (see budget.auto_budget)
SETTING_MINUTES_MIN = 15
SETTING_MINUTES_MAX = 240
BUDGET_MIN = 10  # the database check on `today_dayplan.budget_minutes`
BUDGET_MAX = 300

# ---- estimates --------------------------------------------------------------------------------------------------------------
PROVIDER_EST_MIN = 1
PROVIDER_EST_MAX = 90
OWN_EST_MIN = 1
OWN_EST_MAX = 180
# Defaults per kind of work (PRD Q-F13-12, [VERIFY] with the founder, calibrated from tracked time in R3).
MCQ_SECONDS = 90
RECALL_CARD_SECONDS = 30
PRACTICAL_SECONDS_PER_MARK = 120

# ---- task lifecycle ---------------------------------------------------------------------------------------------------------
UNDO_WINDOW_SECONDS = 60
GRACE_MINUTES = 180  # an event up to 03:00 local may still complete yesterday's open task
SKIP_SUPPRESS_COUNT = 3  # skipped this many times ...
SKIP_SUPPRESS_WINDOW_DAYS = 14  # ... in this many days: suppressed for this many days
SKIP_SUPPRESS_DAYS = 14
MISS_WINDOW_DAYS = 7
SNOOZE_PRESET_DAYS = {"tomorrow": 1, "in_3_days": 3, "next_week": 7}
OWN_CARRY_MAX = 3  # an own task is carried forward this many times, then flagged "stuck"

# ---- quotas -----------------------------------------------------------------------------------------------------------------
OWN_TASKS_PER_DAY = 20
OWN_TASKS_OPEN_FUTURE = 200
OWN_TASK_MAX_DAYS_AHEAD = 30
PREVIEW_MAX_DAYS_AHEAD = 14
PREVIEW_MAX_TASKS = 4
DISABLED_KINDS_MAX = 20
SWAPS_PER_DAY = 20
REGENERATIONS_PER_DAY = 6
HISTORY_MAX_DAYS = 92

# ---- text limits ------------------------------------------------------------------------------------------------------------
TITLE_MAX = 120  # database column; providers are held to PROVIDER_TITLE_MAX
PROVIDER_TITLE_MAX = 80
REASON_MAX = 160  # database column; providers are held to PROVIDER_REASON_MAX
PROVIDER_REASON_MAX = 140
DEDUPE_KEY_MAX = 120
LINK_VALUE_MAX = 200
PAYLOAD_MAX_CHARS = 4096
SELECTION_LOG_MAX_CHARS = 4096

# ---- reasons a candidate is dropped (the keys of `selection_log.dropped`) ---------------------------------------------------
DROP_REASONS = (
    "invalid",
    "invalid_link",
    "est_range",
    "not_enrolled",
    "hidden_kind",
    "expired",
    "done_today",
    "suppressed",
    "duplicate",
    "not_focus",
    "budget",
    "cap",
)
