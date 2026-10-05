import { describe, expect, it } from 'vitest'

import { toChartModel } from './chartData'
import type { Series } from './types'

const series = (legendCount: number): Series => ({
  from: '2026-10-05',
  to: '2026-10-06',
  group: 'day',
  by: 'subject',
  week_start: 1,
  tz: 'Asia/Kolkata',
  legend: Array.from({ length: legendCount }, (_, i) => ({ key: `k${i}`, name: `Subject ${i}` })),
  buckets: [
    { start: '2026-10-05', end: '2026-10-05', seconds: 600, parts: { k0: 100, k1: 200, k6: 300 } },
    { start: '2026-10-06', end: '2026-10-06', seconds: 0, parts: {} },
  ],
})

describe('toChartModel', () => {
  it('draws one series for a total', () => {
    const m = toChartModel(series(3), 'day', 'total')
    expect(m.series).toEqual([{ key: 'seconds', name: 'Study time' }])
    expect(m.columns[0]?.values).toEqual({ seconds: 600 })
  })
  it('keeps up to five named series in order', () => {
    const m = toChartModel(series(3), 'day', 'subject')
    expect(m.series.map((s) => s.key)).toEqual(['k0', 'k1', 'k2'])
    expect(m.columns[0]?.values).toEqual({ k0: 100, k1: 200, __other: 300 })
  })
  it('folds the sixth and later series into Other, never a new colour', () => {
    const m = toChartModel(series(8), 'day', 'subject')
    expect(m.series).toHaveLength(6)
    expect(m.series.at(-1)).toEqual({ key: '__other', name: 'Other' })
    expect(m.columns[0]?.values.__other).toBe(300)
  })
  it('keeps the total of every column', () => {
    const m = toChartModel(series(8), 'day', 'subject')
    const sum = Object.values(m.columns[0]?.values ?? {}).reduce((a, b) => a + b, 0)
    expect(sum).toBe(600)
  })
})
