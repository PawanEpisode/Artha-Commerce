/**
 * Coarse buckets for analytics properties (PRD F-16 section 10). Exact values (a name's length, a coverage percent,
 * an age in minutes) are more identifying than the question needs, so events carry a range instead.
 */

const HOUR = 3_600_000
const DAY = 24 * HOUR

export function lengthBucket(length: number): '1-10' | '11-20' | '21-40' | '41+' {
  if (length <= 10) return '1-10'
  if (length <= 20) return '11-20'
  return length <= 40 ? '21-40' : '41+'
}

/** Chapter coverage in tens of percent: "0-9", "10-19", ... "100". */
export function coverageBucket(percent: number): string {
  const p = Math.min(100, Math.max(0, Math.floor(percent)))
  return p === 100 ? '100' : `${Math.floor(p / 10) * 10}-${Math.floor(p / 10) * 10 + 9}`
}

export function ageBucket(ms: number): '<1h' | '<1d' | '<7d' | '7d+' {
  if (ms < HOUR) return '<1h'
  if (ms < DAY) return '<1d'
  return ms < 7 * DAY ? '<7d' : '7d+'
}

/** Toasts are frequent: successes and info are sampled, errors and warnings are always kept (PRD 10). */
export function toastSampleRate(variant: string): number {
  return variant === 'error' || variant === 'warning' ? 1 : 0.1
}
