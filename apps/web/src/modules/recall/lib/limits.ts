/**
 * Every threshold of the recall domain. Mirrors `apps/api/modules/recall/domain/limits.py` name for name; `limits.test.ts`
 * parses the Python file and fails when the two differ, so change both in one pull request.
 */

export const SCHEDULER_VERSION = 'fsrs-6.0'

// Card memory phase (the same numbers as py-fsrs `State`, plus 0 for a card never reviewed)
export const PHASE_NEW = 0
export const PHASE_LEARNING = 1
export const PHASE_REVIEW = 2
export const PHASE_RELEARNING = 3

// Ratings
export const AGAIN = 1
export const HARD = 2
export const GOOD = 3
export const EASY = 4

export const MINUTES_PER_DAY = 1440.0
export const SECONDS_PER_DAY = 86400.0

// Queue and catch-up
export const IMPORTANCE_WEIGHTS = [1.0, 1.5, 2.0] as const // bullet, important, mandatory
export const CATCHUP_DUE_FACTOR = 2 // catch-up when due reviews exceed this many daily limits ...
export const CATCHUP_OVERDUE_DAYS = 3 // ... or the oldest is this overdue with more than one day of work
export const OVERDUE_PRIORITY_PER_DAY = 0.02
export const OVERDUE_PRIORITY_CAP_DAYS = 30
export const NEW_AFTER_REVIEWS = 3 // one new card after every three reviews when interleaving
export const SUBJECT_WINDOW = 5 // how far ahead the subject alternation may look
export const REVIEW_AHEAD_BATCH = 10
export const MAX_DAYS_TO_CLEAR = 60

// Stability caps and leeches
export const CONTENT_RESET_STABILITY_CAP_DAYS = 3.0
export const LEECH_THRESHOLD = 8
export const LEECH_SUSPEND_DAYS = 7

// Undo, sessions, offline
export const UNDO_MAX_EVENTS = 10
export const UNDO_WINDOW_MINUTES = 30
export const SESSION_IDLE_CLOSE_MINUTES = 60
export const OFFLINE_EVENT_MAX_AGE_DAYS = 30
export const CLOCK_SKEW_MINUTES = 5
export const DURATION_CAP_MS = 600_000
export const OFFLINE_EVENT_CAP = 5000
export const BATCH_MAX_EVENTS = 100

// Forgotten list and streak
export const FORGOTTEN_MIN_SCORE = 2.0
export const FORGOTTEN_LAPSE_WINDOW_DAYS = 30
export const FORGOTTEN_AGAIN_WINDOW_DAYS = 14
export const STREAK_MIN_REVIEWS = 5

// Rebalance
export const REBALANCE_DEFAULT_DAYS = 7
export const REBALANCE_MAX_DAYS_AHEAD = 14
export const REBALANCE_PROTECT_R = 0.7 // mandatory cards below this retrievability are never moved

// Card content
export const FIELD_MAX_CHARS = 4000
export const SHORT_FIELD_MAX_CHARS = 200
export const MAX_CLOZES = 20
export const MAX_TAGS = 12
export const MAX_TAG_CHARS = 40

// Defaults and ranges of the student's settings
export const DEFAULT_RETENTION = 0.9
export const RETENTION_RANGE = [0.8, 0.97] as const
export const DEFAULT_NEW_PER_DAY = 10
export const NEW_PER_DAY_RANGE = [0, 100] as const
export const DEFAULT_REVIEWS_PER_DAY = 100
export const REVIEWS_PER_DAY_RANGE = [20, 500] as const
export const DEFAULT_LEARNING_STEPS = [1, 10] as const
export const DEFAULT_RELEARNING_STEPS = [10] as const
export const MAX_STEP_MINUTES = 1440
export const DEFAULT_MAX_INTERVAL_DAYS = 365
export const MAX_INTERVAL_RANGE = [30, 3650] as const
export const DEFAULT_DAY_START_HOUR = 4
export const DAY_START_HOUR_RANGE = [0, 6] as const
