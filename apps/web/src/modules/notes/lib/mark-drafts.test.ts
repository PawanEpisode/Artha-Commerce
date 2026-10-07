import { describe, expect, it } from 'vitest'

import { toViewportRect } from './coords'
import {
  areaDraft,
  bookmarkDraft,
  clampFontSize,
  inkDraft,
  markupDraft,
  moveRect,
  pinDraft,
  quadsFromClientRects,
  rectFromDrag,
  resizeRect,
  textBoxDraft,
  textBoxRect,
} from './mark-drafts'

const box = { left: 100, top: 50, width: 600, height: 800 }
const client = (x: number, y: number, w: number, h: number) => ({
  left: box.left + x,
  top: box.top + y,
  width: w,
  height: h,
})

describe('geometry from a selection', () => {
  it('gives two quads for two lines, normalised to the page and rounded to five decimals', () => {
    const quads = quadsFromClientRects([client(60, 80, 300, 16), client(60, 100, 180, 16)], box, 0)
    expect(quads).toHaveLength(2)
    expect(quads[0]).toEqual([0.1, 0.1, 0.5, 0.02])
    expect(quads[1]).toEqual([0.1, 0.125, 0.3, 0.02])
    for (const q of quads) for (const n of q) expect(Math.abs(n * 1e5 - Math.round(n * 1e5))).toBeLessThan(1e-6)
  })

  it('merges the pieces of one line', () => {
    const quads = quadsFromClientRects([client(60, 80, 150, 16), client(211, 80, 150, 16)], box, 0)
    expect(quads).toHaveLength(1)
  })

  it('clamps to the page and skips empty rectangles', () => {
    const quads = quadsFromClientRects([client(-30, 80, 100, 16), client(10, 10, 0, 0)], box, 0)
    expect(quads).toHaveLength(1)
    expect(quads[0]?.[0]).toBe(0)
  })

  it('stores the same geometry whatever the view rotation: viewed rectangles map back to the stored frame', () => {
    const stored: [number, number, number, number][] = [
      [0.1, 0.1, 0.5, 0.02],
      [0.1, 0.125, 0.3, 0.02],
    ]
    for (const rotation of [0, 90, 180, 270]) {
      const view = rotation % 180 === 0 ? { width: 600, height: 800, rotation } : { width: 800, height: 600, rotation }
      const viewBox = { left: 100, top: 50, width: view.width, height: view.height }
      const clientRects = stored.map((r) => {
        const [x, y, w, h] = toViewportRect(r, view)
        return { left: viewBox.left + x, top: viewBox.top + y, width: w, height: h }
      })
      const back = quadsFromClientRects(clientRects, viewBox, rotation)
      expect(back).toHaveLength(2)
      back.forEach((q, i) => q.forEach((n, j) => expect(n).toBeCloseTo((stored[i] as number[])[j] as number, 4)))
    }
  })
})

describe('markup drafts', () => {
  const selection = {
    page: 14,
    rects: [[0.1, 0.1, 0.5, 0.02]] as [number, number, number, number][],
    selector: {
      quote_exact: 'ITC blocked credits',
      quote_prefix: 'the ',
      quote_suffix: ' are',
      text_start: 10,
      text_end: 29,
    },
  }

  it('carries the quote that re-attaches it', () => {
    const draft = markupDraft(selection, 'highlight', 'y')
    expect(draft).toMatchObject({
      kind: 'highlight',
      page: 14,
      color: 'y',
      quote_exact: 'ITC blocked credits',
      anchor_engine: 'pdfjs',
    })
  })

  it('refuses a selection with no usable rectangles', () => {
    expect(markupDraft({ ...selection, rects: [] }, 'underline', 'g')).toBeNull()
  })
})

describe('area, pin, bookmark, text box', () => {
  it('rejects a drag that is too small and clamps one that leaves the page', () => {
    expect(rectFromDrag([0.5, 0.5], [0.5005, 0.5005])).toBeNull()
    expect(rectFromDrag([0.9, 0.9], [1.4, 1.4])).toEqual([0.9, 0.9, 0.1, 0.1])
    expect(rectFromDrag([0.5, 0.6], [0.2, 0.3])).toEqual([0.2, 0.3, 0.3, 0.3])
  })

  it('makes each kind with valid geometry', () => {
    expect(areaDraft(2, [0.2, 0.3, 0.3, 0.3], 'b')?.kind).toBe('area')
    expect(pinDraft(2, [0.5, 0.5], 'p')?.kind).toBe('sticky')
    expect(bookmarkDraft(2, 0.4, 'Section 17(5)')).toMatchObject({ kind: 'bookmark', comment: 'Section 17(5)' })
    expect(textBoxDraft(2, textBoxRect([0.5, 0.5]), 'i2')?.kind).toBe('textbox')
    expect(
      inkDraft(
        2,
        [
          {
            pts: [
              [0.1, 0.1],
              [0.2, 0.2],
            ],
            w: 0.0035,
          },
        ],
        'i1',
      )?.kind,
    ).toBe('ink')
  })

  it('keeps a text box inside the page when moved, resized and when its font changes', () => {
    const r = textBoxRect([0.99, 0.99])
    expect(r[0] + r[2]).toBeLessThanOrEqual(1)
    expect(r[1] + r[3]).toBeLessThanOrEqual(1)
    expect(moveRect([0.5, 0.5, 0.3, 0.1], 1, 1)).toEqual([0.7, 0.9, 0.3, 0.1])
    expect(resizeRect([0.8, 0.8, 0.1, 0.1], 1, 1)).toEqual([0.8, 0.8, 0.2, 0.2])
    expect(clampFontSize(1)).toBeLessThanOrEqual(0.06)
    expect(clampFontSize(0)).toBeGreaterThanOrEqual(0.008)
  })
})
