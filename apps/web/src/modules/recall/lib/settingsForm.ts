import { DAY_START_HOUR_RANGE, NEW_PER_DAY_RANGE, RETENTION_RANGE, REVIEWS_PER_DAY_RANGE } from './limits'
import type { RecallSettings } from './schemas'

/** The settings a student edits in release 1, as the form holds them. Retention is a whole percent here. */
export interface SettingsDraft {
  new_per_day: number
  reviews_per_day: number
  retention_percent: number
  day_start_hour: number
  tz: string
  catchup_mode: 'auto' | 'on' | 'off'
  interleave: boolean
  bury_siblings: boolean
  gestures: boolean
  show_intervals: boolean
  improve_scheduler_consent: boolean
}

export const CATCHUP_OPTIONS = [
  { value: 'auto', label: 'Automatic' },
  { value: 'on', label: 'Always on' },
  { value: 'off', label: 'Off' },
] as const

export function draftOf(s: RecallSettings): SettingsDraft {
  return {
    new_per_day: s.new_per_day,
    reviews_per_day: s.reviews_per_day,
    retention_percent: Math.round(s.desired_retention * 100),
    day_start_hour: s.day_start_hour,
    tz: s.tz,
    catchup_mode: (['auto', 'on', 'off'] as const).find((m) => m === s.catchup_mode) ?? 'auto',
    interleave: s.interleave,
    bury_siblings: s.bury_siblings,
    gestures: s.gestures,
    show_intervals: s.show_intervals,
    improve_scheduler_consent: s.improve_scheduler_consent,
  }
}

export type SettingsErrors = Partial<Record<keyof SettingsDraft, string>>

const inRange = (v: number, [lo, hi]: readonly [number, number]) => Number.isInteger(v) && v >= lo && v <= hi

/** Messages in words, with the allowed range, for anything out of bounds. The server checks again. */
export function validate(d: SettingsDraft): SettingsErrors {
  const e: SettingsErrors = {}
  if (!inRange(d.new_per_day, NEW_PER_DAY_RANGE))
    e.new_per_day = `Choose between ${NEW_PER_DAY_RANGE[0]} and ${NEW_PER_DAY_RANGE[1]}.`
  if (!inRange(d.reviews_per_day, REVIEWS_PER_DAY_RANGE))
    e.reviews_per_day = `Choose between ${REVIEWS_PER_DAY_RANGE[0]} and ${REVIEWS_PER_DAY_RANGE[1]}.`
  const [lo, hi] = [Math.round(RETENTION_RANGE[0] * 100), Math.round(RETENTION_RANGE[1] * 100)]
  if (!inRange(d.retention_percent, [lo, hi])) e.retention_percent = `Choose between ${lo}% and ${hi}%.`
  if (!inRange(d.day_start_hour, DAY_START_HOUR_RANGE))
    e.day_start_hour = `Choose an hour between ${DAY_START_HOUR_RANGE[0]} and ${DAY_START_HOUR_RANGE[1]}.`
  if (d.tz.trim() === '') e.tz = 'Enter a time zone such as Asia/Kolkata.'
  return e
}

/** Only what changed, in the API's own field names, so a save never overwrites what another device set. */
export function changes(before: RecallSettings, d: SettingsDraft): Partial<RecallSettings> {
  const base = draftOf(before)
  const out: Partial<RecallSettings> = {}
  if (d.new_per_day !== base.new_per_day) out.new_per_day = d.new_per_day
  if (d.reviews_per_day !== base.reviews_per_day) out.reviews_per_day = d.reviews_per_day
  if (d.retention_percent !== base.retention_percent) out.desired_retention = d.retention_percent / 100
  if (d.day_start_hour !== base.day_start_hour) out.day_start_hour = d.day_start_hour
  if (d.tz.trim() !== base.tz) out.tz = d.tz.trim()
  if (d.catchup_mode !== base.catchup_mode) out.catchup_mode = d.catchup_mode
  for (const key of [
    'interleave',
    'bury_siblings',
    'gestures',
    'show_intervals',
    'improve_scheduler_consent',
  ] as const) {
    if (d[key] !== base[key]) out[key] = d[key]
  }
  return out
}

export const VACATION_MAX_DAYS = 60
