/**
 * Page layout and the window of pages to draw, for the continuous vertical reader. Everything is computed from page
 * sizes in points (`page_meta`), the zoom and the width of the reading area, so placeholders have their final size
 * before a page is drawn and nothing jumps. Pure, no DOM.
 */
import type { ZoomSpec } from './reader-schema'
import { scaleFor } from './reader-zoom'

export interface PageBox {
  w: number
  h: number
}

export interface Layout {
  /** Top edge of each page in CSS pixels, from the top of the scrolling content. */
  tops: number[]
  widths: number[]
  heights: number[]
  /** CSS pixels per PDF point, per page. */
  scales: number[]
  /** Height of all the content. */
  total: number
  /** Width the content needs: the widest page plus padding. */
  contentWidth: number
  gap: number
  pad: number
  /** Space above the first page and below the last, where the reader's bars sit. */
  padTop: number
  padBottom: number
}

export interface LayoutOptions {
  /** Width of the reading area. */
  availWidth: number
  gap?: number
  pad?: number
  padTop?: number
  padBottom?: number
}

export const DEFAULT_GAP = 12
export const DEFAULT_PAD = 8
/** Fit width stops here on wide screens: a line of 1200 px is not comfortable to read and one page would fill the screen. */
export const MAX_FIT_WIDTH = 920

/** The width one fitted page gets in a reading area `clientWidth` wide (the same maths as `computeLayout`). */
export const fitWidthFor = (clientWidth: number, pad = DEFAULT_PAD) =>
  Math.min(MAX_FIT_WIDTH, Math.max(1, clientWidth - pad * 2))

export function computeLayout(sizes: ReadonlyArray<PageBox>, zoom: ZoomSpec, options: LayoutOptions): Layout {
  const gap = options.gap ?? DEFAULT_GAP
  const pad = options.pad ?? DEFAULT_PAD
  const padTop = options.padTop ?? pad
  const padBottom = options.padBottom ?? pad
  const inner = zoom === 'fit' ? fitWidthFor(options.availWidth, pad) : Math.max(1, options.availWidth - pad * 2)
  const tops: number[] = []
  const widths: number[] = []
  const heights: number[] = []
  const scales: number[] = []
  let y = padTop
  let widest = 0
  for (const size of sizes) {
    const scale = scaleFor(zoom, inner, size.w)
    const w = Math.round(size.w * scale)
    const h = Math.round(size.h * scale)
    tops.push(y)
    widths.push(w)
    heights.push(h)
    scales.push(scale)
    y += h + gap
    widest = Math.max(widest, w)
  }
  const total = sizes.length ? y - gap + padBottom : padTop + padBottom
  return {
    tops,
    widths,
    heights,
    scales,
    total,
    contentWidth: Math.max(options.availWidth, widest + pad * 2),
    gap,
    pad,
    padTop,
    padBottom,
  }
}

/** Index of the last page whose top is at or above `y` (binary search); 0 when above the first page. */
export function pageIndexAt(layout: Layout, y: number): number {
  let lo = 0
  let hi = layout.tops.length - 1
  while (lo < hi) {
    const mid = (lo + hi + 1) >> 1
    if ((layout.tops[mid] as number) <= y) lo = mid
    else hi = mid - 1
  }
  return Math.max(0, lo)
}

/** First and last (0-based, inclusive) pages that overlap the viewport, or null for an empty document. */
export function visibleRange(layout: Layout, scrollTop: number, viewHeight: number): [number, number] | null {
  const n = layout.tops.length
  if (n === 0) return null
  const bottom = scrollTop + viewHeight
  let first = pageIndexAt(layout, scrollTop)
  if ((layout.tops[first] as number) + (layout.heights[first] as number) <= scrollTop && first < n - 1) first += 1
  const last = pageIndexAt(layout, Math.max(scrollTop, bottom - 1))
  return [Math.min(first, last), last]
}

export interface PageWindow {
  /** Pages (0-based) with a canvas: the visible ones nearest the middle plus `ahead` below, at most `maxLive`. */
  live: number[]
  /** Pages with a placeholder box in the DOM: the live ones plus a margin, so scrolling never finds a hole. */
  mounted: [number, number] | null
}

export interface WindowOptions {
  maxLive?: number
  /** Pages drawn ahead of the last visible page (default 1) and behind the first (default 0). */
  ahead?: number
  behind?: number
  /** Extra placeholder pages kept in the DOM on each side of the live ones. */
  margin?: number
}

/**
 * The visible pages plus one ahead hold canvases (about five at most); a few more placeholders stay mounted. When more
 * pages are visible than `maxLive` (zoomed far out), the ones nearest the middle of the viewport win.
 */
export function pageWindow(
  layout: Layout,
  scrollTop: number,
  viewHeight: number,
  options: WindowOptions = {},
): PageWindow {
  const maxLive = options.maxLive ?? 5
  const ahead = options.ahead ?? 1
  const behind = options.behind ?? 0
  const margin = options.margin ?? 2
  const range = visibleRange(layout, scrollTop, viewHeight)
  if (!range) return { live: [], mounted: null }
  const n = layout.tops.length
  const from = Math.max(0, range[0] - behind)
  const to = Math.min(n - 1, range[1] + ahead)
  let live: number[] = []
  for (let i = from; i <= to; i++) live.push(i)
  if (live.length > maxLive) {
    const mid = scrollTop + viewHeight / 2
    const centreOf = (i: number) => (layout.tops[i] as number) + (layout.heights[i] as number) / 2
    live = [...live].sort((a, b) => Math.abs(centreOf(a) - mid) - Math.abs(centreOf(b) - mid)).slice(0, maxLive)
    live.sort((a, b) => a - b)
  }
  return { live, mounted: [Math.max(0, from - margin), Math.min(n - 1, to + margin)] }
}

/** Where `y` falls: a page and how far down it (0 to 1). Used to keep the same spot when zoom or sizes change. */
export interface Anchor {
  index: number
  /** Distance from the page top as a fraction of its height (may be negative in the gap above, or above 1). */
  frac: number
}

export function anchorAt(layout: Layout, y: number): Anchor {
  if (layout.tops.length === 0) return { index: 0, frac: 0 }
  const index = pageIndexAt(layout, y)
  const h = Math.max(1, layout.heights[index] as number)
  return { index, frac: (y - (layout.tops[index] as number)) / h }
}

export function yForAnchor(layout: Layout, anchor: Anchor): number {
  if (layout.tops.length === 0) return 0
  const index = Math.min(anchor.index, layout.tops.length - 1)
  return (layout.tops[index] as number) + anchor.frac * (layout.heights[index] as number)
}

/**
 * The page the student is on: the one under a probe line a little below the top of the viewport, and the last page when
 * scrolled to the end. Stable under `scrollToPage`, which puts a page's top just above the viewport.
 */
export function currentPageAt(layout: Layout, scrollTop: number, viewHeight: number): number {
  const n = layout.tops.length
  if (n === 0) return 0
  if (scrollTop + viewHeight >= layout.total - 2 && scrollTop > 0) return n - 1
  return pageIndexAt(layout, scrollTop + Math.min(viewHeight * 0.25, 120))
}

/** Scroll offset that puts page `index` just below the top bar (`padTop`), where a reader with bars shown expects it. */
export function scrollTopForPage(layout: Layout, index: number): number {
  if (layout.tops.length === 0) return 0
  const i = Math.min(Math.max(0, index), layout.tops.length - 1)
  return Math.max(0, (layout.tops[i] as number) - layout.padTop)
}

/** Clamp a page number to 1..count (count 0 gives 1). */
export const clampPage = (page: number, count: number) =>
  Math.min(Math.max(1, Math.round(page) || 1), Math.max(1, count))
