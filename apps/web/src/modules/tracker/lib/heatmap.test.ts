import { describe, expect, it } from 'vitest'

import { heatCells, intensity } from './heatmap'

describe('intensity', () => {
  it('steps up at 1 s, 30 m, 90 m, 3 h and 5 h', () => {
    expect([0, 1, 1799, 1800, 5399, 5400, 10799, 10800, 17999, 18000, 90000].map(intensity)).toEqual([
      0, 1, 1, 2, 2, 3, 3, 4, 4, 5, 5,
    ])
  })
})

describe('heatCells', () => {
  it('lists every day of the range, with empty days at level 0', () => {
    const cells = heatCells([{ date: '2026-10-06', seconds: 3600 }], '2026-10-05', '2026-10-07', 1)
    expect(cells.map((c) => [c.date, c.level, c.weekday])).toEqual([
      ['2026-10-05', 0, 0],
      ['2026-10-06', 2, 1],
      ['2026-10-07', 0, 2],
    ])
    expect(cells[1]?.label).toContain('1 h')
    expect(cells[0]?.label).toContain('no study')
  })
  it('puts Sunday first when the week starts on Sunday', () => {
    const cells = heatCells([], '2026-10-04', '2026-10-05', 0)
    expect(cells.map((c) => c.weekday)).toEqual([0, 1])
  })
})
