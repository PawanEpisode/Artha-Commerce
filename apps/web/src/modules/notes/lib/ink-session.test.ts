import { describe, expect, it } from 'vitest'

import {
  addStroke,
  finishStroke,
  inkGeometry,
  joinsDrawing,
  redoStroke,
  type TimedPoint,
  undoStroke,
} from './ink-session'
import { BURST_GAP_MS } from './simplify'

const pts = (n: number, t0 = 0): TimedPoint[] =>
  Array.from({ length: n }, (_, i) => ({ x: 0.1 + i * 0.01, y: 0.2 + Math.sin(i / 3) * 0.02, t: t0 + i * 8 }))
const stroke = (t0: number, n = 20) => {
  const s = finishStroke(pts(n, t0), 0.0035)
  if (!s) throw new Error('no stroke')
  return s
}

describe('finishStroke', () => {
  it('simplifies, rounds to five decimals and keeps the times', () => {
    const s = stroke(100, 200)
    expect(s.pts.length).toBeLessThan(200)
    expect(s.t0).toBe(100)
    for (const [x, y] of s.pts) {
      expect(Math.abs(x * 1e5 - Math.round(x * 1e5))).toBeLessThan(1e-6)
      expect(y).toBeGreaterThanOrEqual(0)
    }
  })

  it('keeps a tap as a dot', () => {
    expect(finishStroke([{ x: 0.5, y: 0.5, t: 0 }], 0.0035)?.pts).toHaveLength(1)
  })

  it('returns null for no points', () => {
    expect(finishStroke([], 0.0035)).toBeNull()
  })
})

describe('burst grouping', () => {
  const next = { page: 1, color: 'i1' as const, newId: () => 'mark-1' }

  it('joins strokes within the burst gap into one drawing, and splits on a pause, another page or another colour', () => {
    const first = addStroke(null, { ...next, stroke: stroke(0) })
    expect(first.created).toBe(true)
    const end = first.drawing.strokes[0]?.t1 ?? 0
    const joined = addStroke(first.drawing, { ...next, stroke: stroke(end + BURST_GAP_MS - 10) })
    expect(joined.created).toBe(false)
    expect(joined.drawing.strokes).toHaveLength(2)
    expect(addStroke(first.drawing, { ...next, stroke: stroke(end + BURST_GAP_MS + 500) }).created).toBe(true)
    expect(addStroke(first.drawing, { ...next, page: 2, stroke: stroke(end + 10) }).created).toBe(true)
    expect(addStroke(first.drawing, { ...next, color: 'i2', stroke: stroke(end + 10) }).created).toBe(true)
    expect(joinsDrawing(null, 1, 'i1', stroke(0))).toBe(false)
  })
})

describe('undo and redo', () => {
  it('takes the newest stroke back and brings it forward again', () => {
    const a = addStroke(null, { page: 1, color: 'i1', newId: () => 'm', stroke: stroke(0) })
    const b = addStroke(a.drawing, { page: 1, color: 'i1', newId: () => 'm', stroke: stroke(100) })
    const undone = undoStroke(b.drawing)
    expect(undone.drawing.strokes).toHaveLength(1)
    expect(undone.removed).not.toBeNull()
    expect(redoStroke(undone.drawing).strokes).toHaveLength(2)
    const empty = undoStroke(undoStroke(b.drawing).drawing)
    expect(empty.drawing.strokes).toHaveLength(0)
    expect(undoStroke(empty.drawing).removed).toBeNull()
  })

  it('a new stroke clears the redo history', () => {
    const a = addStroke(null, { page: 1, color: 'i1', newId: () => 'm', stroke: stroke(0) })
    const undone = undoStroke(a.drawing).drawing
    const again = addStroke(
      { ...undone, strokes: [stroke(0)] },
      { page: 1, color: 'i1', newId: () => 'm', stroke: stroke(50) },
    )
    expect(again.drawing.redo).toEqual([])
  })
})

describe('geometry of a drawing', () => {
  it('has strokes within the page and a box around them', () => {
    const g = inkGeometry([stroke(0), stroke(50)])
    expect(g.strokes).toHaveLength(2)
    const [x, y, w, h] = g.bbox
    expect(x).toBeGreaterThanOrEqual(0)
    expect(y).toBeGreaterThanOrEqual(0)
    expect(x + w).toBeLessThanOrEqual(1)
    expect(y + h).toBeLessThanOrEqual(1)
  })
})
