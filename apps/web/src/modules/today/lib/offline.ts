/**
 * What the screen says about a plan that came from this device's cache (PRD 7.3, FR-F13-41). Pure.
 *
 * - `fresh`: saved less than 6 hours ago, on today's date.
 * - `stale`: saved 6 hours ago or more, still today's date: "Updated 7 h ago. Refresh".
 * - `previous_day`: the plan is of an earlier date than the student's today: shown dimmed as a recap, actions disabled.
 */
export const STALE_AFTER_MS = 6 * 3_600_000

export type CacheStatus = 'fresh' | 'stale' | 'previous_day'

/** The calendar date (`YYYY-MM-DD`) of a moment in a time zone; the device zone when the zone name is unknown. */
export function dateIn(ms: number, tz: string): string {
  const date = new Date(ms)
  try {
    const parts = new Intl.DateTimeFormat('en-CA', { timeZone: tz, year: 'numeric', month: '2-digit', day: '2-digit' })
      .formatToParts(date)
      .reduce<Record<string, string>>((acc, p) => ({ ...acc, [p.type]: p.value }), {})
    return `${parts.year}-${parts.month}-${parts.day}`
  } catch {
    const pad = (n: number) => String(n).padStart(2, '0')
    return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`
  }
}

export function cacheStatus(entry: { savedAt: number; planDate: string; tz: string }, nowMs: number): CacheStatus {
  if (dateIn(nowMs, entry.tz) !== entry.planDate) return 'previous_day'
  return nowMs - entry.savedAt >= STALE_AFTER_MS ? 'stale' : 'fresh'
}

/** "Updated 7 h ago" (hours once past the first hour, minutes before). */
export function updatedAgo(savedAt: number, nowMs: number): string {
  const minutes = Math.max(0, Math.round((nowMs - savedAt) / 60_000))
  if (minutes < 1) return 'Updated just now'
  if (minutes < 60) return `Updated ${minutes} min ago`
  return `Updated ${Math.floor(minutes / 60)} h ago`
}

/** True once the student's own day has moved past the plan on screen (the check runs every minute and on focus). */
export const dayRolledOver = (planDate: string, tz: string, nowMs: number) => dateIn(nowMs, tz) > planDate

export type Banner =
  | { kind: 'none' }
  | { kind: 'offline'; waiting: number }
  | { kind: 'syncing'; waiting: number }
  | { kind: 'stale'; label: string }
  | { kind: 'previous_day' }
  | { kind: 'updating' }

/**
 * Which one banner to show, most important first: a plan of an earlier day, then offline, then syncing, then stale, then the quiet
 * "Updating" while a cached plan is refreshed.
 */
export function bannerFor(input: {
  online: boolean
  waiting: number
  /** Present when the plan on screen came from the cache. */
  cache: { status: CacheStatus; savedAt: number } | null
  refreshing: boolean
  now: number
}): Banner {
  const { online, waiting, cache, refreshing, now } = input
  if (cache?.status === 'previous_day') return { kind: 'previous_day' }
  if (!online) return { kind: 'offline', waiting }
  if (waiting > 0) return { kind: 'syncing', waiting }
  if (cache?.status === 'stale') return { kind: 'stale', label: updatedAgo(cache.savedAt, now) }
  if (cache && refreshing) return { kind: 'updating' }
  return { kind: 'none' }
}
