import { describe, expect, it } from 'vitest'

import {
  anchorAt,
  clampPage,
  computeLayout,
  currentPageAt,
  MAX_FIT_WIDTH,
  pageIndexAt,
  pageWindow,
  scrollTopForPage,
  visibleRange,
  yForAnchor,
} from './reader-layout'

const A4 = { w: 595, h: 842 }
const pages = (n: number, size = A4) => Array.from({ length: n }, () => size)

describe('computeLayout', () => {
  it('stacks pages at their final size at fit width', () => {
    const l = computeLayout(pages(3), 'fit', { availWidth: 376, gap: 10, pad: 8 })
    // inner width 360, scale 360 / 595
    expect(l.widths[0]).toBe(360)
    expect(l.heights[0]).toBe(Math.round(842 * (360 / 595)))
    expect(l.tops[0]).toBe(8)
    expect(l.tops[1]).toBe(8 + (l.heights[0] as number) + 10)
    expect(l.total).toBe((l.tops[2] as number) + (l.heights[2] as number) + 8)
    expect(l.contentWidth).toBe(376)
  })

  it('stops fit width at a readable width on a wide screen and centres the pages', () => {
    const l = computeLayout(pages(2), 'fit', { availWidth: 1280 })
    expect(l.widths[0]).toBe(MAX_FIT_WIDTH)
  })

  it('fits each page to the width, so a landscape page does not overflow', () => {
    const l = computeLayout([A4, { w: 842, h: 595 }], 'fit', { availWidth: 376 })
    expect(l.widths[0]).toBe(360)
    expect(l.widths[1]).toBe(360)
  })

  it('widens the content when a zoomed page is wider than the area, so it pans', () => {
    const l = computeLayout(pages(2), 200, { availWidth: 376 })
    expect(l.widths[0]).toBe(1190)
    expect(l.contentWidth).toBe(1190 + 16)
  })

  it('leaves room for the bars above and below', () => {
    const l = computeLayout(pages(1), 'fit', { availWidth: 376, padTop: 64, padBottom: 112 })
    expect(l.tops[0]).toBe(64)
    expect(l.total).toBe(64 + (l.heights[0] as number) + 112)
    expect(scrollTopForPage(l, 0)).toBe(0)
  })

  it('has a size for an empty document', () => {
    const l = computeLayout([], 'fit', { availWidth: 376 })
    expect(l.tops).toEqual([])
    expect(l.total).toBe(16)
    expect(visibleRange(l, 0, 800)).toBeNull()
    expect(pageWindow(l, 0, 800)).toEqual({ live: [], mounted: null })
  })
})

describe('visible window', () => {
  const l = computeLayout(pages(100), 'fit', { availWidth: 376, gap: 10, pad: 8 })
  const h = l.heights[0] as number

  it('finds the pages that overlap the viewport', () => {
    expect(visibleRange(l, 0, 500)).toEqual([0, 0])
    const mid = (l.tops[10] as number) + 5
    expect(visibleRange(l, mid, 600)).toEqual([10, 11])
    expect(pageIndexAt(l, (l.tops[50] as number) + h)).toBe(50)
  })

  it('skips a page that has just scrolled out of sight', () => {
    expect(visibleRange(l, (l.tops[3] as number) + h + 1, 400)?.[0]).toBe(4)
  })

  it('holds canvases for the visible pages plus one ahead, and no more than five', () => {
    const w = pageWindow(l, l.tops[20] as number, 500)
    expect(w.live).toEqual([20, 21])
    expect(w.mounted).toEqual([18, 23])
    const tiny = computeLayout(pages(100), 25, { availWidth: 800 })
    const many = pageWindow(tiny, 4000, 5000, { maxLive: 5 })
    expect(many.live.length).toBe(5)
    const sorted = [...many.live].sort((a, b) => a - b)
    expect(many.live).toEqual(sorted)
  })

  it('prefetches two pages in large mode', () => {
    const w = pageWindow(l, l.tops[20] as number, 500, { ahead: 2 })
    expect(w.live).toEqual([20, 21, 22])
  })

  it('stays inside the document at both ends', () => {
    expect(pageWindow(l, 0, 500).mounted?.[0]).toBe(0)
    const end = pageWindow(l, l.total - 500, 500)
    expect(end.mounted?.[1]).toBe(99)
    expect(Math.max(...end.live)).toBe(99)
  })

  it('scrolling through 100 pages never holds more than five canvases', () => {
    let worst = 0
    for (let y = 0; y < l.total; y += 137) worst = Math.max(worst, pageWindow(l, y, 800).live.length)
    expect(worst).toBeLessThanOrEqual(5)
  })
})

describe('anchors and the current page', () => {
  const l = computeLayout(pages(10), 'fit', { availWidth: 376, padTop: 64 })

  it('keeps a spot across a zoom change', () => {
    const y = (l.tops[4] as number) + (l.heights[4] as number) * 0.25
    const anchor = anchorAt(l, y)
    expect(anchor.index).toBe(4)
    expect(anchor.frac).toBeCloseTo(0.25, 2)
    const bigger = computeLayout(pages(10), 200, { availWidth: 376, padTop: 64 })
    expect(yForAnchor(bigger, anchor)).toBeCloseTo((bigger.tops[4] as number) + (bigger.heights[4] as number) * 0.25, 0)
  })

  it('reports the page under the top of the viewport, and the last page at the end', () => {
    expect(currentPageAt(l, 0, 700)).toBe(0)
    expect(currentPageAt(l, scrollTopForPage(l, 5), 700)).toBe(5)
    expect(currentPageAt(l, l.total - 700, 700)).toBe(9)
  })

  it('clamps page numbers', () => {
    expect(clampPage(0, 10)).toBe(1)
    expect(clampPage(11, 10)).toBe(10)
    expect(clampPage(Number.NaN, 10)).toBe(1)
    expect(clampPage(5, 0)).toBe(1)
  })
})
