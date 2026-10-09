/** Words and numbers for the recall screens. Pure, so the sentences can be tested. */

export const plural = (n: number, one: string, many = `${one}s`) => `${n} ${n === 1 ? one : many}`

/** "About 12 min", "About 1 h 20 min": the plan's estimate, rounded. */
export function estimate(minutes: number): string {
  const m = Math.max(0, Math.round(minutes))
  if (m < 1) return 'Under a minute'
  if (m < 60) return `About ${m} min`
  const h = Math.floor(m / 60)
  const rest = m % 60
  return rest === 0 ? `About ${h} h` : `About ${h} h ${rest} min`
}

/**
 * How long a backlog will take, in kind words. A big number alone is discouraging and says nothing useful, so a backlog is
 * given as days of work at the student's own daily limit (capped by the server at 60).
 */
export function backlogSentence(due: number, daysToClear: number | null): string {
  if (due <= 0) return 'Nothing is waiting.'
  if (daysToClear === null || daysToClear <= 1) return `${plural(due, 'card')} to go. That is one sitting.`
  return `${plural(due, 'card')} are waiting. At your daily limit that clears in about ${daysToClear} days.`
}

export const percent = (v: number | null | undefined, digits = 0): string =>
  v === null || v === undefined ? 'Not enough reviews yet' : `${(v * 100).toFixed(digits)}%`

export const STATE_LABELS: Record<number, string> = { 0: 'New', 1: 'Learning', 2: 'Review', 3: 'Relearning' }

export const MODE_LABELS: Record<string, string> = {
  normal: 'Normal',
  catchup: 'Catch-up',
  review_ahead: 'Reviewing ahead',
}

/** "Tue 6 Oct" from an ISO date, in UTC so the label never shifts by the device's zone. */
export function shortDate(iso: string): string {
  const d = new Date(`${iso}T00:00:00Z`)
  return d.toLocaleDateString('en-IN', { weekday: 'short', day: 'numeric', month: 'short', timeZone: 'UTC' })
}

export const dayOfMonth = (iso: string): string => String(Number(iso.slice(8, 10)))

export function minutesLabel(seconds: number): string {
  const m = Math.round(seconds / 60)
  if (m < 1) return seconds > 0 ? 'Under a minute' : '0 min'
  return m < 60 ? `${m} min` : `${Math.floor(m / 60)} h ${m % 60} min`
}
