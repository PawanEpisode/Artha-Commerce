import { formatDuration as formatMinutes } from '@artha/design-system'

/** Formatting and arithmetic for study time. Pure; the server stays the clock and these only mirror its maths. */

/** "2 h 5 m", "45 m", "0 m". Seconds are floored to whole minutes, as the rollups store whole seconds. */
export function formatDuration(totalSeconds: number): string {
  return formatMinutes(Math.floor(Math.max(0, totalSeconds) / 60))
}

/** Spoken form for screen readers: "2 hours 5 minutes". */
export function spokenDuration(totalSeconds: number): string {
  const seconds = Math.max(0, Math.floor(totalSeconds))
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  const parts = []
  if (h) parts.push(`${h} ${h === 1 ? 'hour' : 'hours'}`)
  if (m || !h) parts.push(`${m} ${m === 1 ? 'minute' : 'minutes'}`)
  return parts.join(' ')
}

/** "01:05:09" for the running clock. */
export function formatClock(totalSeconds: number): string {
  const s = Math.max(0, Math.floor(totalSeconds))
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${pad(Math.floor(s / 3600))}:${pad(Math.floor((s % 3600) / 60))}:${pad(s % 60)}`
}

export interface Clocked {
  status: 'running' | 'paused'
  started_at: string
  paused_at: string | null
  paused_total_seconds: number
}

/** Counted seconds of a stopwatch at `nowMs` (server-corrected). Wall time up to now or the pause, minus pauses. */
export function elapsedSeconds(sw: Clocked, nowMs: number): number {
  const start = Date.parse(sw.started_at)
  const end = sw.paused_at ? Math.min(nowMs, Date.parse(sw.paused_at)) : nowMs
  return Math.max(0, Math.floor((end - start) / 1000) - sw.paused_total_seconds)
}

/** The student's calendar date (YYYY-MM-DD) for an instant in a time zone. */
export function localDate(instant: Date | number, tz: string): string {
  return new Intl.DateTimeFormat('en-CA', { timeZone: tz, year: 'numeric', month: '2-digit', day: '2-digit' }).format(
    instant,
  )
}

/** Adds days to an ISO date. UTC arithmetic, so it ignores daylight saving. */
export function addDays(iso: string, days: number): string {
  const d = new Date(`${iso}T00:00:00Z`)
  d.setUTCDate(d.getUTCDate() + days)
  return d.toISOString().slice(0, 10)
}

export const daysBetween = (a: string, b: string) => Math.round((Date.parse(b) - Date.parse(a)) / 86_400_000)

/** 0 = Monday ... 6 = Sunday, for an ISO date. */
export const weekdayOf = (iso: string) => (new Date(`${iso}T00:00:00Z`).getUTCDay() + 6) % 7

/** First day of the week containing `iso`. `weekStart` 1 = Monday, 0 = Sunday. */
export function weekStartOf(iso: string, weekStart: 0 | 1): string {
  const back = weekStart === 1 ? weekdayOf(iso) : (weekdayOf(iso) + 1) % 7
  return addDays(iso, -back)
}

/** "datetime-local" input value (YYYY-MM-DDTHH:mm) for an instant, shown in a time zone. */
export function toLocalInput(instant: Date | number, tz: string): string {
  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone: tz,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hourCycle: 'h23',
  }).formatToParts(instant)
  const get = (t: string) => parts.find((p) => p.type === t)?.value ?? '00'
  return `${get('year')}-${get('month')}-${get('day')}T${get('hour')}:${get('minute')}`
}

/** Instant for a "datetime-local" value read as wall-clock time in `tz`. Resolves daylight saving by search. */
export function fromLocalInput(value: string, tz: string): Date {
  const asUtc = Date.parse(`${value}:00Z`)
  let guess = asUtc
  for (let i = 0; i < 3; i++) {
    const shown = Date.parse(`${toLocalInput(guess, tz)}:00Z`)
    guess += asUtc - shown
  }
  return new Date(guess)
}
