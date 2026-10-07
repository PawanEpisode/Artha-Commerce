/**
 * Geometry of the text layer, no React and no pdf.js: where each run goes, which rectangles a text range covers, and
 * what a browser selection means in page terms. The page text and the offsets come from `PdfTextContent`
 * (pdf.js text or OCR words), so a mark made on either engine's text uses the same frame (`lib/coords.ts`) and the same
 * quote rules (`lib/anchors.ts`).
 */
import { makeSelector, type Selector } from '../anchors'
import { mergeAdjacentQuads, type Rect, round5 } from '../geometry'
import type { LayerItem, PdfTextContent } from './index'

export const MAX_LAYER_ITEMS = 4000

/** What the reader reports for a selection inside one page: the text, where it is, and how to find it again. */
export interface PageSelection {
  page: number
  text: string
  /** Offsets into the page text of this engine (hints; `selector` is what survives re-extraction). */
  start: number
  end: number
  /** Rectangles in the stored frame (normalised to the unrotated page, five decimals), one per line, merged. */
  rects: Rect[]
  selector: Selector
}

export interface ItemStyle {
  left: number
  top: number
  /** Font size as a fraction of the page height. */
  fontFraction: number
  /** Horizontal stretch that makes the browser's glyphs as wide as the run in the file. */
  scaleX: number
  angle: number
}

/** `measureEm(str)` is the width of `str` in a 1 px font (any fixed sans font); without it the run is not stretched. */
export function itemStyle(item: LayerItem, pageW: number, pageH: number, measureEm?: (s: string) => number): ItemStyle {
  let scaleX = 1
  const em = measureEm?.(item.str) ?? 0
  if (em > 0 && item.w > 0 && item.h > 0) {
    const targetPoints = item.w * pageW
    const naturalPoints = em * item.h * pageH
    scaleX = Math.min(8, Math.max(0.05, targetPoints / naturalPoints))
  }
  return { left: item.x, top: item.y, fontFraction: item.h, scaleX, angle: item.angle }
}

/**
 * Rectangles (normalised frame) covering page-text offsets `[start, end)`, from the runs' boxes, splitting a run in
 * proportion to its characters. An approximation of the glyphs, good for a search hit; selections use the DOM instead.
 */
export function rectsForRange(items: ReadonlyArray<LayerItem>, start: number, end: number): Rect[] {
  const rects: Rect[] = []
  if (end <= start) return rects
  for (const item of items) {
    const itemEnd = item.start + item.str.length
    if (item.str.length === 0 || itemEnd <= start || item.start >= end) continue
    const from = Math.max(start, item.start) - item.start
    const to = Math.min(end, itemEnd) - item.start
    const lo = from / item.str.length
    const hi = to / item.str.length
    rects.push([round5(item.x + lo * item.w), round5(item.y), round5((hi - lo) * item.w), round5(item.h)])
  }
  return rects
}

/** Browser client rectangles to the normalised frame of the page box, dropping empty ones and merging a line's pieces. */
export function rectsToFrame(
  clientRects: ReadonlyArray<{ left: number; top: number; width: number; height: number }>,
  box: { left: number; top: number; width: number; height: number },
): Rect[] {
  if (box.width <= 0 || box.height <= 0) return []
  const clamp = (n: number) => Math.min(1, Math.max(0, n))
  const rects: Rect[] = []
  for (const r of clientRects) {
    if (r.width < 0.5 || r.height < 0.5) continue
    const x = clamp((r.left - box.left) / box.width)
    const y = clamp((r.top - box.top) / box.height)
    const w = clamp((r.left + r.width - box.left) / box.width) - x
    const h = clamp((r.top + r.height - box.top) / box.height) - y
    if (w > 0 && h > 0) rects.push([round5(x), round5(y), round5(w), round5(h)])
  }
  return mergeAdjacentQuads(rects)
}

/** An endpoint of a DOM selection: the run it falls in and the character offset inside that run's text. */
export interface Endpoint {
  /** `data-start` of the run's element. */
  runStart: number
  offset: number
}

/** Page-text offsets of a selection from its two endpoints (in either order), or null when it selects nothing. */
export function selectionOffsets(a: Endpoint, b: Endpoint): { start: number; end: number } | null {
  const x = a.runStart + a.offset
  const y = b.runStart + b.offset
  const start = Math.min(x, y)
  const end = Math.max(x, y)
  return end > start ? { start, end } : null
}

/** Builds the `PageSelection` for offsets in a page's text. */
export function selectionFor(
  page: number,
  content: Pick<PdfTextContent, 'text'>,
  offsets: { start: number; end: number },
  rects: Rect[],
): PageSelection {
  const text = content.text.slice(offsets.start, offsets.end)
  return {
    page,
    text,
    start: offsets.start,
    end: offsets.end,
    rects,
    selector: makeSelector(content.text, offsets.start, offsets.end),
  }
}
