"""
Every threshold of the recall domain in one place (ERD section 4, "Importance weight, thresholds"). Mirrored byte for
byte in `apps/web/src/modules/recall/lib/limits.ts`; a parity test compares the two, so change both in one pull request.
"""

from __future__ import annotations

SCHEDULER_VERSION = "fsrs-6.0"

# Card memory phase (the same numbers as py-fsrs `State`, plus 0 for a card never reviewed)
PHASE_NEW, PHASE_LEARNING, PHASE_REVIEW, PHASE_RELEARNING = 0, 1, 2, 3

# Ratings
AGAIN, HARD, GOOD, EASY = 1, 2, 3, 4

MINUTES_PER_DAY = 1440.0
SECONDS_PER_DAY = 86400.0

# Queue and catch-up
IMPORTANCE_WEIGHTS = (1.0, 1.5, 2.0)  # bullet, important, mandatory
CATCHUP_DUE_FACTOR = 2  # catch-up when due reviews exceed this many daily limits ...
CATCHUP_OVERDUE_DAYS = 3  # ... or the oldest is this overdue with more than one day of work
OVERDUE_PRIORITY_PER_DAY = 0.02
OVERDUE_PRIORITY_CAP_DAYS = 30
NEW_AFTER_REVIEWS = 3  # one new card after every three reviews when interleaving
SUBJECT_WINDOW = 5  # how far ahead the subject alternation may look
REVIEW_AHEAD_BATCH = 10
MAX_DAYS_TO_CLEAR = 60

# Stability caps and leeches
CONTENT_RESET_STABILITY_CAP_DAYS = 3.0
LEECH_THRESHOLD = 8
LEECH_SUSPEND_DAYS = 7

# Undo, sessions, offline
UNDO_MAX_EVENTS = 10
UNDO_WINDOW_MINUTES = 30
SESSION_IDLE_CLOSE_MINUTES = 60
OFFLINE_EVENT_MAX_AGE_DAYS = 30
CLOCK_SKEW_MINUTES = 5
DURATION_CAP_MS = 600_000
OFFLINE_EVENT_CAP = 5000
BATCH_MAX_EVENTS = 100

# Forgotten list and streak
FORGOTTEN_MIN_SCORE = 2.0
FORGOTTEN_LAPSE_WINDOW_DAYS = 30
FORGOTTEN_AGAIN_WINDOW_DAYS = 14
STREAK_MIN_REVIEWS = 5

# Rebalance
REBALANCE_DEFAULT_DAYS = 7
REBALANCE_MAX_DAYS_AHEAD = 14
REBALANCE_PROTECT_R = 0.7  # mandatory cards below this retrievability are never moved

# Card content
FIELD_MAX_CHARS = 4000
SHORT_FIELD_MAX_CHARS = 200
MAX_CLOZES = 20
MAX_TAGS = 12
MAX_TAG_CHARS = 40

# Defaults and ranges of the student's settings
DEFAULT_RETENTION = 0.90
RETENTION_RANGE = (0.80, 0.97)
DEFAULT_NEW_PER_DAY = 10
NEW_PER_DAY_RANGE = (0, 100)
DEFAULT_REVIEWS_PER_DAY = 100
REVIEWS_PER_DAY_RANGE = (20, 500)
DEFAULT_LEARNING_STEPS = (1, 10)
DEFAULT_RELEARNING_STEPS = (10,)
MAX_STEP_MINUTES = 1440
DEFAULT_MAX_INTERVAL_DAYS = 365
MAX_INTERVAL_RANGE = (30, 3650)
DEFAULT_DAY_START_HOUR = 4
DAY_START_HOUR_RANGE = (0, 6)
