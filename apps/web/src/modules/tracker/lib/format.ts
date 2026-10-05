import { ACTIVITY_OPTIONS, type ActivityType } from './types'

export const activityLabel = (a: ActivityType | string) =>
  ACTIVITY_OPTIONS.find((o) => o.value === a)?.label ?? a.replace(/_/g, ' ')

/** "9:05 am" in the student's tracker time zone. */
export function timeOfDay(iso: string, tz: string): string {
  return new Intl.DateTimeFormat('en-IN', { hour: 'numeric', minute: '2-digit', hour12: true, timeZone: tz })
    .format(new Date(iso))
    .toLowerCase()
}

const LONG = new Intl.DateTimeFormat('en-IN', {
  weekday: 'short',
  day: 'numeric',
  month: 'short',
  year: 'numeric',
  timeZone: 'UTC',
})
/** "Mon, 5 Oct 2026" for an ISO date. */
export const dayLabel = (iso: string) => LONG.format(new Date(`${iso}T00:00:00Z`))

const SHORT = new Intl.DateTimeFormat('en-IN', { day: 'numeric', month: 'short', timeZone: 'UTC' })
export const shortDay = (iso: string) => SHORT.format(new Date(`${iso}T00:00:00Z`))

export const WEEKDAYS_MON = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'] as const
export const WEEKDAYS_SUN = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'] as const

const WALL = new Intl.DateTimeFormat('en-IN', {
  weekday: 'short',
  day: 'numeric',
  month: 'short',
  year: 'numeric',
  hour: 'numeric',
  minute: '2-digit',
  hour12: true,
  timeZone: 'UTC',
})
const LOCAL_INPUT = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/
/** "Mon, 5 Oct 2026, 11:05 pm" for a "datetime-local" value (wall-clock time, so no zone shift). Empty when unset. */
export function friendlyDateTime(local: string): string {
  if (!LOCAL_INPUT.test(local)) return ''
  const ms = Date.parse(`${local}:00Z`)
  if (Number.isNaN(ms)) return ''
  const part = (type: Intl.DateTimeFormatPartTypes) =>
    WALL.formatToParts(new Date(ms)).find((p) => p.type === type)?.value ?? ''
  return `${part('weekday')}, ${part('day')} ${part('month')} ${part('year')}, ${part('hour')}:${part('minute')} ${part('dayPeriod').toLowerCase()}`
}
