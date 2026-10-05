/**
 * Limits the tracker enforces. They mirror apps/api/modules/tracking/domain/durations.py and reports.py; a test on
 * the API side (test_web_parity.py) reads this file and fails when the two drift. Keep one `NAME = value` per line.
 */
export const MIN_SESSION_SECONDS = 60
export const MAX_SESSION_SECONDS = 43200
export const MAX_MANUAL_SPAN_SECONDS = 86400
export const CONFIRM_OLDER_THAN_DAYS = 60
export const REJECT_OLDER_THAN_DAYS = 365
export const CLOCK_SKEW_SECONDS = 300
export const UNDO_SECONDS = 10
export const IDLE_ANSWER_SECONDS = 120
export const MERGE_MAX_GAP_SECONDS = 1800
export const OFFLINE_START_MAX_AGE_SECONDS = 43200
export const NOTE_MAX_CHARS = 500
export const IDLE_MINUTES_MIN = 5
export const IDLE_MINUTES_MAX = 60
export const GOAL_DAILY_MIN = 15
export const GOAL_DAILY_MAX = 1440
export const GOAL_WEEKLY_MIN = 30
export const GOAL_WEEKLY_MAX = 10080
/** Seconds at which the calendar heat map steps up a level. Level 0 is "no study". */
export const HEATMAP_EDGES_SECONDS = [1, 1800, 5400, 10800, 18000] as const
