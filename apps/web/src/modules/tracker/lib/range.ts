import { addDays, daysBetween, weekStartOf } from './duration'

export const RANGE_PRESETS = ['today', '7d', '30d', '90d', 'week', 'custom'] as const
export type RangePreset = (typeof RANGE_PRESETS)[number]

export const PRESET_LABELS: Record<RangePreset, string> = {
  today: 'Today',
  '7d': '7 days',
  '30d': '30 days',
  '90d': '90 days',
  week: 'This week',
  custom: 'Custom',
}

export interface DateRange {
  from: string
  to: string
}

/** The date range a preset stands for, ending on `today`. Custom keeps whatever range it is given. */
export function presetRange(preset: RangePreset, today: string, weekStart: 0 | 1 = 1, custom?: DateRange): DateRange {
  switch (preset) {
    case 'today':
      return { from: today, to: today }
    case '7d':
      return { from: addDays(today, -6), to: today }
    case '30d':
      return { from: addDays(today, -29), to: today }
    case '90d':
      return { from: addDays(today, -89), to: today }
    case 'week':
      return { from: weekStartOf(today, weekStart), to: today }
    case 'custom':
      return custom ?? { from: addDays(today, -29), to: today }
  }
}

/** Day buckets for up to a year; a longer range has to be shown by week or month. Mirrors the API. */
export const MAX_DAY_RANGE_DAYS = 366

export function rangeProblem(range: DateRange): string | null {
  if (range.from > range.to) return 'The start date must be on or before the end date.'
  if (daysBetween(range.from, range.to) + 1 > MAX_DAY_RANGE_DAYS * 5) return 'Choose a range of five years or less.'
  return null
}

/** The best chart grouping for a range: days for up to 31, weeks for up to a year, months beyond. */
export function defaultGroup(range: DateRange): 'day' | 'week' | 'month' {
  const days = daysBetween(range.from, range.to) + 1
  return days <= 31 ? 'day' : days <= 366 ? 'week' : 'month'
}
