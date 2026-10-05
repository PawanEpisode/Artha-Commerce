import { dayLabel, shortDay } from './format'
import type { Group, Series, SplitBy } from './types'

/** At most this many named series are drawn; the rest fold into "Other" (never a sixth colour). */
export const MAX_SERIES = 5
const OTHER = '__other'

export interface ChartModel {
  series: Array<{ key: string; name: string }>
  columns: Array<{ label: string; short: string; values: Record<string, number> }>
}

/** Turns a series report into bars: one series for a total, or the named parts with the tail folded into Other. */
export function toChartModel(data: Series, group: Group, by: SplitBy): ChartModel {
  const total = by === 'total' || data.legend.length === 0
  const named = data.legend.slice(0, MAX_SERIES)
  const folded = data.legend.length > MAX_SERIES
  const top = new Set(named.map((l) => l.key))
  const series = total
    ? [{ key: 'seconds', name: 'Study time' }]
    : folded
      ? [...named, { key: OTHER, name: 'Other' }]
      : named
  const columns = data.buckets.map((b) => {
    const values: Record<string, number> = {}
    if (total) values.seconds = b.seconds
    else
      for (const [key, seconds] of Object.entries(b.parts)) {
        const target = top.has(key) ? key : OTHER
        values[target] = (values[target] ?? 0) + seconds
      }
    return {
      label: group === 'day' ? dayLabel(b.start) : `${shortDay(b.start)} to ${shortDay(b.end)}`,
      short: shortDay(b.start),
      values,
    }
  })
  return { series, columns }
}
