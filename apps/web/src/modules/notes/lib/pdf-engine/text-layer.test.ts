import { describe, expect, it } from 'vitest'

import type { LayerItem } from './index'
import { itemStyle, rectsForRange, rectsToFrame, selectionFor, selectionOffsets } from './text-layer'

const items: LayerItem[] = [
  { str: 'Input tax', x: 0.1, y: 0.1, w: 0.18, h: 0.015, angle: 0, start: 0 },
  { str: 'credit', x: 0.1, y: 0.13, w: 0.12, h: 0.015, angle: 0, start: 10 },
]

describe('itemStyle', () => {
  it('stretches a run so the browser text is as wide as the file text', () => {
    // 1 px font: the string is 5 px wide; the run is 0.1 * 600 = 60 pt wide with a 12 pt font on an 800 pt page.
    const s = itemStyle({ str: 'abcde', x: 0.1, y: 0.2, w: 0.1, h: 12 / 800, angle: 0, start: 0 }, 600, 800, () => 5)
    expect(s.scaleX).toBeCloseTo(60 / (5 * 12))
    expect(s.left).toBe(0.1)
    expect(s.fontFraction).toBeCloseTo(0.015)
  })

  it('does not stretch without a measurement, and bounds a wild one', () => {
    expect(itemStyle(items[0] as LayerItem, 600, 800).scaleX).toBe(1)
    expect(itemStyle({ ...(items[0] as LayerItem), w: 0.9 }, 600, 800, () => 0.01).scaleX).toBe(8)
  })
})

describe('rectsForRange', () => {
  it('covers a whole run, a part of one, and spans two runs', () => {
    const whole = rectsForRange(items, 0, 9)
    expect(whole).toEqual([[0.1, 0.1, 0.18, 0.015]])
    const part = rectsForRange(items, 6, 9)
    expect(part[0]?.[0]).toBeCloseTo(0.1 + (6 / 9) * 0.18, 4)
    expect(part[0]?.[2]).toBeCloseTo((3 / 9) * 0.18, 4)
    expect(rectsForRange(items, 6, 13)).toHaveLength(2)
  })

  it('finds nothing outside the text', () => {
    expect(rectsForRange(items, 20, 30)).toEqual([])
    expect(rectsForRange(items, 5, 5)).toEqual([])
  })
})

describe('rectsToFrame', () => {
  const box = { left: 100, top: 50, width: 400, height: 800 }

  it('converts client rectangles to the page frame', () => {
    const r = rectsToFrame([{ left: 140, top: 130, width: 80, height: 16 }], box)
    expect(r).toEqual([[0.1, 0.1, 0.2, 0.02]])
  })

  it('drops empty and clamps to the page', () => {
    expect(rectsToFrame([{ left: 140, top: 130, width: 0, height: 16 }], box)).toEqual([])
    const clamped = rectsToFrame([{ left: 80, top: 40, width: 100, height: 40 }], box)
    expect(clamped[0]?.[0]).toBe(0)
    expect(clamped[0]?.[1]).toBe(0)
  })

  it('merges the pieces of one line', () => {
    const r = rectsToFrame(
      [
        { left: 140, top: 130, width: 40, height: 16 },
        { left: 180, top: 130, width: 40, height: 16 },
      ],
      box,
    )
    expect(r).toHaveLength(1)
    expect(r[0]?.[2]).toBeCloseTo(0.2, 4)
  })

  it('has nothing for an empty page box', () => {
    expect(rectsToFrame([{ left: 0, top: 0, width: 5, height: 5 }], { left: 0, top: 0, width: 0, height: 0 })).toEqual(
      [],
    )
  })
})

describe('selections', () => {
  it('turns two endpoints, in either order, into offsets', () => {
    expect(selectionOffsets({ runStart: 0, offset: 6 }, { runStart: 10, offset: 4 })).toEqual({ start: 6, end: 14 })
    expect(selectionOffsets({ runStart: 10, offset: 4 }, { runStart: 0, offset: 6 })).toEqual({ start: 6, end: 14 })
    expect(selectionOffsets({ runStart: 0, offset: 3 }, { runStart: 0, offset: 3 })).toBeNull()
  })

  it('carries the text and the quote the anchoring needs', () => {
    const text = 'Input tax\ncredit is blocked for motor vehicles.\n'
    const sel = selectionFor(14, { text }, { start: 0, end: 9 }, [[0.1, 0.1, 0.18, 0.015]])
    expect(sel.page).toBe(14)
    expect(sel.text).toBe('Input tax')
    expect(sel.selector.quote_exact).toBe('Input tax')
    expect(sel.selector.quote_suffix).toContain('credit')
    expect(sel.rects).toEqual([[0.1, 0.1, 0.18, 0.015]])
  })
})
