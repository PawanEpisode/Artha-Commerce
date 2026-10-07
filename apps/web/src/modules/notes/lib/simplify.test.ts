import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

import { describe, expect, it } from 'vitest'

import { MAX_POINTS } from './geometry'
import { groupBursts, limitPoints, type Point, simplifyPoints, simplifyStroke } from './simplify'

interface Stroke {
  pts: Point[]
  w: number
}
// The same fixtures the Python tests use: the two implementations must agree on every case.
const fixtures = JSON.parse(
  readFileSync(
    fileURLToPath(new URL('../../../../../api/modules/notes/tests/fixtures/simplify_cases.json', import.meta.url)),
    'utf8',
  ),
) as {
  rdp: { name: string; pts: Point[]; tolerance?: number; expected: Point[] }[]
  bursts: {
    name: string
    strokes: { id: string; t0: number; t1: number }[]
    gap_ms?: number
    max_strokes?: number
    expected: string[][]
  }[]
  limit: { name: string; strokes: Stroke[]; max_points: number; expected: Stroke[] }[]
}

describe('simplifyPoints', () => {
  it.each(fixtures.rdp.map((c) => [c.name, c] as const))('%s', (_n, c) => {
    expect(simplifyPoints(c.pts, c.tolerance)).toEqual(c.expected)
  })
})

describe('groupBursts', () => {
  it.each(fixtures.bursts.map((c) => [c.name, c] as const))('%s', (_n, c) => {
    const strokes = c.strokes.map((s) => ({ ...s, pts: [[0.1, 0.1]] as Point[], w: 0.0035 }))
    expect(groupBursts(strokes, c.gap_ms, c.max_strokes).map((g) => g.map((s) => s.id))).toEqual(c.expected)
  })
})

describe('limitPoints', () => {
  it.each(fixtures.limit.map((c) => [c.name, c] as const))('%s', (_n, c) => {
    expect(limitPoints(c.strokes, c.max_points)).toEqual(c.expected)
  })

  it('brings a dense drawing under the geometry limit', () => {
    const pts = Array.from({ length: 30_000 }, (_, i): Point => [(i % 997) / 997, ((i * 31) % 991) / 991])
    const out = limitPoints([{ pts, w: 0.0035 }])
    expect(out.reduce((n, s) => n + s.pts.length, 0)).toBeLessThanOrEqual(MAX_POINTS)
  })

  it('never mutates its input', () => {
    const stroke = {
      pts: [
        [0.1, 0.1],
        [0.2, 0.2],
        [0.3, 0.1],
      ] as Point[],
      w: 0.0035,
      t0: 1,
    }
    const before = JSON.stringify(stroke)
    simplifyStroke(stroke)
    limitPoints([stroke], 2)
    expect(JSON.stringify(stroke)).toBe(before)
  })
})
