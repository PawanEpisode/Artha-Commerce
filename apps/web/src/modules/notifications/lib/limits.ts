/**
 * Limits the API enforces that the screen has to respect. They mirror `DEFAULT_THROTTLE_RATES["notifications_test"]` in
 * apps/api/config/settings.py (`limits.test.ts` reads that file and fails when they drift) and the active-device
 * limit of PRD 11 (Q9). Keep one `NAME = value` per line.
 */
export const MAX_ACTIVE_DEVICES = 10
export const TEST_PUSH_PER_MINUTE = 5
/** How long the test button rests after a 429 that did not say how long to wait. */
export const TEST_COOLDOWN_SECONDS = 60
/** The most seconds a `Retry-After` can make the button rest, so a bad header cannot lock it for hours. */
export const TEST_COOLDOWN_MAX_SECONDS = 300
/** How long a registration refresh is skipped after a successful one (the settings screen always refreshes). */
export const RESYNC_MIN_INTERVAL_MS = 12 * 60 * 60 * 1000
