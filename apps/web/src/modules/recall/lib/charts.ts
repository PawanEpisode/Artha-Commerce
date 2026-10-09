import type { ChartColumn } from '@artha/design-system'

import { dayOfMonth, shortDate } from './format'
import type { StatsChapters, StatsForecast, StatsRetention, StatsSummary } from './schemas'

/** Columns for the bar charts, one per day. Pure, so the shapes and the words can be tested. */
export const reviewColumns = (s: StatsSummary): ChartColumn[] =>
  s.series.map((d) => ({ label: shortDate(d.date), short: dayOfMonth(d.date), values: { reviews: d.reviews } }))

export const retentionColumns = (r: StatsRetention): ChartColumn[] =>
  r.series.map((d) => ({
    label: shortDate(d.date),
    short: dayOfMonth(d.date),
    values: { retention: Math.round(d.retention * 100) },
  }))

export const forecastColumns = (f: StatsForecast): ChartColumn[] =>
  f.days.map((d) => ({ label: shortDate(d.date), short: dayOfMonth(d.date), values: { due: d.due } }))

export type Strength = { label: 'Strong' | 'Okay' | 'Needs revision' | 'Not started'; value: number }

/** How well a chapter is remembered, in words, from the average chance of recalling its cards today. */
export function strengthOf(strength: number | null): Strength {
  if (strength === null) return { label: 'Not started', value: 0 }
  const value = Math.round(strength * 100)
  return { label: strength >= 0.9 ? 'Strong' : strength >= 0.7 ? 'Okay' : 'Needs revision', value }
}

export const chapterTitle = (c: StatsChapters['chapters'][number]): string =>
  c.chapter?.name ?? (c.chapter ? 'Chapter' : 'No chapter')
