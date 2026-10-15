import { track } from '~/modules/observability'

import schema from './event-schema.json'

/** Analytics of Today (PRD section 10). Names and property names come from `event-schema.json`, the same file the API checks. */

type Spec = { where: 'web' | 'api'; props: string[] }
const EVENTS = schema.events as Record<string, Spec>

export const WEB_EVENTS = Object.keys(EVENTS).filter((name) => EVENTS[name].where === 'web')

export type TodayEvent = (typeof WEB_EVENTS)[number]
export type Props = Record<string, string | number | boolean | string[] | null>

/** `0-5`, `6-15`, `16-30`, `31-60`, `61+`. */
export function minutesBucket(minutes: number): string {
  const [a, b, c, d] = [5, 15, 30, 60]
  if (minutes <= a) return schema.buckets.minutes[0]
  if (minutes <= b) return schema.buckets.minutes[1]
  if (minutes <= c) return schema.buckets.minutes[2]
  if (minutes <= d) return schema.buckets.minutes[3]
  return schema.buckets.minutes[4]
}

/** `lt1s`, `1-3s`, `3-10s`, `10-30s`, `30s+`. */
export function timeBucket(ms: number): string {
  if (ms < 1000) return schema.buckets.time[0]
  if (ms < 3000) return schema.buckets.time[1]
  if (ms < 10_000) return schema.buckets.time[2]
  if (ms < 30_000) return schema.buckets.time[3]
  return schema.buckets.time[4]
}

/** Backlog sizes: `1-5`, `6-20`, `21+`. */
export const backlogBucket = (n: number) => (n <= 5 ? '1-5' : n <= 20 ? '6-20' : '21+')

/** Days to exam: `<=14`, `15-60`, `61-120`, `121+`, `none`. */
export function examBucket(days: number | null): string {
  if (days === null) return 'none'
  if (days <= 14) return '<=14'
  if (days <= 60) return '15-60'
  if (days <= 120) return '61-120'
  return '121+'
}

/**
 * The properties an event may carry, and nothing else: unknown names are dropped (a task title can never leave through here).
 * Returns what was kept, or null for an event that is not a web event of the schema.
 */
export function conform(name: string, props: Props): { kept: Props; dropped: string[] } | null {
  const spec = EVENTS[name]
  if (!spec || spec.where !== 'web') return null
  const allowed = new Set(spec.props)
  const kept: Props = {}
  const dropped: string[] = []
  for (const [key, value] of Object.entries(props)) {
    if (allowed.has(key)) kept[key] = value
    else dropped.push(key)
  }
  return { kept, dropped }
}

/** Sends one event of the schema. A no-op for anything else. Never throws. */
export function trackToday(name: string, props: Props = {}): Props | null {
  const result = conform(name, props)
  if (!result) return null
  try {
    track(name, result.kept)
  } catch {
    /* analytics never breaks the screen */
  }
  return result.kept
}
