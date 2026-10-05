import { addDays, daysBetween, formatDuration, weekdayOf } from './duration'
import { HEATMAP_EDGES_SECONDS } from './limits'

/** Heat level 0..5 for a day's seconds. Same edges as the API (parity test). */
export function intensity(seconds: number): number {
  return HEATMAP_EDGES_SECONDS.reduce((level, edge) => (seconds >= edge ? level + 1 : level), 0)
}

const SHORT_DATE = new Intl.DateTimeFormat('en-IN', {
  day: 'numeric',
  month: 'short',
  year: 'numeric',
  timeZone: 'UTC',
})
export const shortDate = (iso: string) => SHORT_DATE.format(new Date(`${iso}T00:00:00Z`))

/** Every day from `from` to `to` as a heat cell, with its position in a week row that starts on `weekStart`. */
export function heatCells(
  days: Array<{ date: string; seconds: number }>,
  from: string,
  to: string,
  weekStart: 0 | 1 = 1,
) {
  const byDate = new Map(days.map((d) => [d.date, d.seconds]))
  const count = daysBetween(from, to) + 1
  return Array.from({ length: Math.max(0, count) }, (_, i) => {
    const date = addDays(from, i)
    const seconds = byDate.get(date) ?? 0
    const weekday = weekStart === 1 ? weekdayOf(date) : (weekdayOf(date) + 1) % 7
    return {
      date,
      level: intensity(seconds),
      weekday,
      label: `${shortDate(date)}: ${seconds > 0 ? formatDuration(seconds) : 'no study'}`,
    }
  })
}
