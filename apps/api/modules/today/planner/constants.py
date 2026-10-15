"""
Every number of the R2 planner (ERD "Planner (R2)") and the closed lists the database checks.

Nothing here imports Django. All values are defaults to tune in beta and are `[VERIFY]` with the founder: they decide when a
student is told "at risk", so they should be reviewed against real plans before the `today_planner` flag opens.
"""

from __future__ import annotations

PLANNER_VERSION = 1  # stored in `StudyPlan.params["v"]` so an old plan can still be explained after a constant changes

# ---- enumerations (closed lists: the database has CHECK constraints for them) -----------------------------------------------
PLAN_STATUSES = ("active", "superseded", "archived")
HEALTHS = ("unknown", "on_track", "slightly_behind", "at_risk")
MILESTONE_KINDS = ("finish_reading", "first_revision", "mock", "exam_week")
PAPER_MILESTONE_KINDS = ("finish_reading", "first_revision", "mock")  # one per paper; `exam_week` is one per plan
MILESTONE_STATUSES = ("pending", "done", "at_risk", "missed", "dropped")
OPEN_MILESTONE_STATUSES = ("pending", "at_risk")
REPLAN_TRIGGERS = ("missed_days", "weekly", "manual", "exam_date", "scheme_switch")
AUTOMATIC_TRIGGERS = ("missed_days", "weekly")  # the others are a student or system action and ignore the minimum gap
OPTIONS = ("more_time", "skim_low_weight", "next_attempt")
OPTION_CHOICES = (*OPTIONS, "none")  # `none`: the student looked at the options and kept the plan as it is

# ---- inputs (ERD 2.6) -------------------------------------------------------------------------------------------------------
DAILY_MINUTES_MIN = 30  # the database check on `today_studyplan.daily_minutes`
DAILY_MINUTES_MAX = 720
UTILISATION_PCT_DEFAULT = 70  # share of study time realistically usable [VERIFY]
UTILISATION_PCT_MIN = 30
UTILISATION_PCT_MAX = 100
LEARN_SHARE_PCT_DEFAULT = (
    70  # share of usable time spent on reading new chapters (the rest is revision and practice) [VERIFY]
)
LEARN_SHARE_PCT_MIN = 10
LEARN_SHARE_PCT_MAX = 100
LANES_DEFAULT = 2  # papers read in parallel [VERIFY]
LANES_MAX = 4
EXAM_WEEK_DAYS_DEFAULT = 7  # the last days before the exam: no new reading [VERIFY]
EXAM_WEEK_DAYS_MAX = (
    7  # fixed at one week until a student setting exists: the mock window (deadline + 7) must end where it starts
)
DEFAULT_CHAPTER_MINUTES = 60  # `syllabus_chapter.est_study_minutes` is optional: 60 when missing

# ---- windows and dates ------------------------------------------------------------------------------------------------------
READING_BUFFER_MIN_DAYS = 14  # reading ends at least this long before the exam [VERIFY]
READING_BUFFER_PCT = (
    30  # and at the latest at 70 percent of the runway: buffer = max(14, round(30 percent of the days)) [VERIFY]
)
FIRST_REVISION_GAP_DAYS = 7  # first revision of a paper starts a week after its reading ends [VERIFY]
MOCK_GAP_DAYS = 7  # the mocks follow the reading deadline by a week [VERIFY]

# ---- health (FR-F13-48) -----------------------------------------------------------------------------------------------------
SLIGHTLY_BEHIND_PCT = (
    10  # a shortfall up to this share of the capacity is "slightly behind"; above it "at risk" [VERIFY]
)

# ---- re-plan (FR-F13-49) ----------------------------------------------------------------------------------------------------
REPLAN_MISSED_DAYS = 2  # consecutive missed local days that trigger a re-plan [VERIFY]
REPLAN_MIN_GAP_DAYS = 3  # automatic re-plans are at least this many days apart [VERIFY]
REPLAN_WEEKDAY = 0  # Monday, in the student's own time zone (`date.weekday()`)
SKIM_FACTOR_PCT = 50  # "skim" halves the estimate of a chapter [VERIFY]
SUMMARY_MAX_CHARS = 8192  # `today_replanevent.summary` (ERD 2.8: at most 8 KB)
SUMMARY_MAX_MOVED = 60  # the list of moved milestones in the summary is cut here (a plan has about 25)
SUMMARY_MAX_SKIM_CHAPTERS = 40  # the skim option names at most this many chapters (the count is always exact)
