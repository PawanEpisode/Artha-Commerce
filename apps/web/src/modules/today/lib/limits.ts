/**
 * Limits Today enforces. They mirror apps/api/modules/today/domain/constants.py; a test on the API side
 * (modules/today/tests/test_web_parity.py) reads this file and fails when the two drift. One `NAME = value` per line.
 */
export const MAX_TASKS = 8
export const MIN_TASKS = 3
export const SETTING_MINUTES_MIN = 15
export const SETTING_MINUTES_MAX = 240
export const FOCUS_PAPERS_SETTING_MAX = 4
export const OWN_EST_MIN = 1
export const OWN_EST_MAX = 180
export const TITLE_MAX = 120
export const UNDO_WINDOW_SECONDS = 60
export const SKIP_SUPPRESS_COUNT = 3
export const SKIP_SUPPRESS_DAYS = 14
export const OWN_TASKS_PER_DAY = 20
export const OWN_TASK_MAX_DAYS_AHEAD = 30
export const OWN_CARRY_MAX = 3
export const PREVIEW_MAX_DAYS_AHEAD = 14
export const SWAPS_PER_DAY = 20
export const REGENERATIONS_PER_DAY = 6
export const HISTORY_MAX_DAYS = 92
