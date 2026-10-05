import { formatDuration } from '@artha/design-system'

/**
 * Presets and limits of the Pomodoro timer. They mirror apps/api/modules/focus/domain/timing.py; a test on the API side
 * (test_web_parity.py) reads this file and fails when the two drift. Keep one `NAME = value` per line, and one preset
 * per line as `key: [focus, short break, long break, rounds before a long break],`.
 */
export const FOCUS_MINUTES_MIN = 5
export const FOCUS_MINUTES_MAX = 120
export const SHORT_BREAK_MINUTES_MIN = 1
export const SHORT_BREAK_MINUTES_MAX = 30
export const LONG_BREAK_MINUTES_MIN = 5
export const LONG_BREAK_MINUTES_MAX = 60
export const ROUNDS_BEFORE_LONG_MIN = 2
export const ROUNDS_BEFORE_LONG_MAX = 8
export const EXTEND_SECONDS = 300
export const MAX_EXTENSIONS = 3
export const PRESENCE_WINDOW_SECONDS = 120
export const MIN_ROUND_SECONDS = 60
export const HEARTBEAT_SECONDS = 20

export const PRESET_VALUES = {
  classic: [25, 5, 15, 4],
  deep: [50, 10, 20, 3],
  light: [15, 3, 10, 4],
} as const

export type PresetKey = keyof typeof PRESET_VALUES | 'custom'

export interface Timings {
  focus_minutes: number
  short_break_minutes: number
  long_break_minutes: number
  rounds_before_long: number
}

export const PRESET_LABELS: Record<PresetKey, string> = {
  classic: 'Classic',
  deep: 'Deep',
  light: 'Light',
  custom: 'Custom',
}

export function presetTimings(key: Exclude<PresetKey, 'custom'>): Timings {
  const [focus, short, long, rounds] = PRESET_VALUES[key]
  return { focus_minutes: focus, short_break_minutes: short, long_break_minutes: long, rounds_before_long: rounds }
}

/** "25 min focus, 5 min break, then a 15 min long break after 4 rounds." */
export function describeTimings(t: Timings): string {
  const d = (minutes: number) => formatDuration(minutes)
  return `${d(t.focus_minutes)} focus, ${d(t.short_break_minutes)} break, then a ${d(t.long_break_minutes)} long break after ${t.rounds_before_long} rounds.`
}

/** Which preset these timings are, or "custom". */
export function matchPreset(t: Timings): PresetKey {
  for (const key of Object.keys(PRESET_VALUES) as Array<keyof typeof PRESET_VALUES>) {
    const p = presetTimings(key)
    if (
      p.focus_minutes === t.focus_minutes &&
      p.short_break_minutes === t.short_break_minutes &&
      p.long_break_minutes === t.long_break_minutes &&
      p.rounds_before_long === t.rounds_before_long
    )
      return key
  }
  return 'custom'
}

/** Field messages for custom timings outside the limits. Empty when everything is allowed. */
export function timingErrors(t: Timings): Partial<Record<keyof Timings, string>> {
  const out: Partial<Record<keyof Timings, string>> = {}
  const check = (k: keyof Timings, lo: number, hi: number, label: string, isDuration = true) => {
    if (Number.isInteger(t[k]) && t[k] >= lo && t[k] <= hi) return
    out[k] = isDuration
      ? `${label} must be between ${formatDuration(lo, 'long')} and ${formatDuration(hi, 'long')}.`
      : `${label} must be between ${lo} and ${hi}.`
  }
  check('focus_minutes', FOCUS_MINUTES_MIN, FOCUS_MINUTES_MAX, 'Focus length')
  check('short_break_minutes', SHORT_BREAK_MINUTES_MIN, SHORT_BREAK_MINUTES_MAX, 'Short break')
  check('long_break_minutes', LONG_BREAK_MINUTES_MIN, LONG_BREAK_MINUTES_MAX, 'Long break')
  check('rounds_before_long', ROUNDS_BEFORE_LONG_MIN, ROUNDS_BEFORE_LONG_MAX, 'Rounds before a long break', false)
  return out
}
