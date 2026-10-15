/** Small, pure helpers for the Today header. Dates are the student's local day, which the server decides (plan.tz). */

export type DayPart = 'morning' | 'afternoon' | 'evening'

/** The hour (0-23) at `iso` in `tz`. Falls back to the device zone when `tz` is not a known zone. */
export function hourIn(iso: string, tz: string): number {
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return 12
  try {
    const part = new Intl.DateTimeFormat('en-GB', { hour: '2-digit', hourCycle: 'h23', timeZone: tz })
      .formatToParts(date)
      .find((p) => p.type === 'hour')
    return Number(part?.value ?? date.getHours()) % 24
  } catch {
    return date.getHours()
  }
}

export function dayPart(hour: number): DayPart {
  if (hour < 12) return 'morning'
  if (hour < 17) return 'afternoon'
  return 'evening'
}

export function greeting(part: DayPart, name?: string | null): string {
  const hello = `Good ${part}`
  return name ? `${hello}, ${name}` : hello
}

/** "45 min", "1 h", "1 h 30 min". */
export function formatMinutes(minutes: number): string {
  const m = Math.max(0, Math.round(minutes))
  if (m < 60) return `${m} min`
  const h = Math.floor(m / 60)
  const rest = m % 60
  return rest ? `${h} h ${rest} min` : `${h} h`
}

/** "Wed 14 Oct" for a `YYYY-MM-DD` day, read as a calendar date (never shifted by the device zone). */
export function formatDay(day: string): string {
  const [y, m, d] = day.split('-').map(Number)
  if (!y || !m || !d) return day
  return new Intl.DateTimeFormat('en-GB', { weekday: 'short', day: 'numeric', month: 'short', timeZone: 'UTC' }).format(
    new Date(Date.UTC(y, m - 1, d)),
  )
}

export function examCountdown(days: number | null): string | null {
  if (days === null || days < 0) return null
  if (days === 0) return 'Exam day'
  return days === 1 ? '1 day to your exam' : `${days} days to your exam`
}
