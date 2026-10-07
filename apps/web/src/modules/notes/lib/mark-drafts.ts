/**
 * Turns what the student did (a text selection, a drag, a tap, a pen stroke) into the draft of a mark: geometry in the
 * stored frame (`coords.ts`), validated with the same rules as the server (`geometry.ts`), plus the text quote
 * (`anchors.ts`). Pure: the screen decides the colour and the tool, this decides the shape.
 */
import type { AnchorEngine, ColorKey, InkColor, MarkDraft, MarkupColor } from './annotation-types'
import { fromViewportRect, type Viewport } from './coords'
import {
  inkBbox,
  MAX_FONT,
  MAX_STROKE_W,
  mergeAdjacentQuads,
  MIN_FONT,
  MIN_RECT_H,
  MIN_RECT_W,
  MIN_STROKE_W,
  type Rect,
  round5,
  type Stroke,
  validateGeometry,
} from './geometry'
import type { PageSelection } from './pdf-engine/text-layer'

export const MAX_COMMENT = 2000
/** Text box defaults: a third of the page wide, two lines of 1.8% of the page height. */
export const TEXT_BOX = { w: 0.34, h: 0.06, fs: 0.018 } as const
/** Pen widths as a fraction of the page width. */
export const PEN_WIDTHS = { thin: 0.002, medium: 0.0035, thick: 0.007 } as const
export type PenWidth = keyof typeof PEN_WIDTHS

const clamp01 = (n: number) => Math.min(1, Math.max(0, n))

/** Client rectangles of a selection (screen pixels) to quads in the stored frame, for a page shown at any rotation. */
export function quadsFromClientRects(
  clientRects: ReadonlyArray<{ left: number; top: number; width: number; height: number }>,
  box: { left: number; top: number; width: number; height: number },
  rotation: number,
): Rect[] {
  if (box.width <= 0 || box.height <= 0) return []
  const view: Viewport = { width: box.width, height: box.height, rotation }
  const quads: Rect[] = []
  for (const r of clientRects) {
    if (r.width < 0.5 || r.height < 0.5) continue
    const x = clamp01((r.left - box.left) / box.width) * box.width
    const y = clamp01((r.top - box.top) / box.height) * box.height
    const w = clamp01((r.left + r.width - box.left) / box.width) * box.width - x
    const h = clamp01((r.top + r.height - box.top) / box.height) * box.height - y
    if (w > 0 && h > 0) quads.push(fromViewportRect([x, y, w, h], view))
  }
  return mergeAdjacentQuads(quads)
}

/** A highlight or underline from a text selection: merged line rectangles plus the quote that re-attaches it. */
export function markupDraft(
  selection: Pick<PageSelection, 'page' | 'rects' | 'selector'>,
  kind: 'highlight' | 'underline',
  color: MarkupColor,
  engine: AnchorEngine = 'pdfjs',
): MarkDraft | null {
  const check = validateGeometry(kind, { quads: selection.rects })
  if (!check.geometry) return null
  const s = selection.selector
  return {
    kind,
    page: selection.page,
    geometry: check.geometry,
    color,
    quote_exact: s.quote_exact,
    quote_prefix: s.quote_prefix,
    quote_suffix: s.quote_suffix,
    text_start: s.text_start,
    text_end: s.text_end,
    anchor_engine: engine,
  }
}

/** The rectangle between two corners of a drag, clamped to the page; null when it is too small to be meant. */
export function rectFromDrag(a: [number, number], b: [number, number]): Rect | null {
  const x0 = clamp01(Math.min(a[0], b[0]))
  const y0 = clamp01(Math.min(a[1], b[1]))
  const x1 = clamp01(Math.max(a[0], b[0]))
  const y1 = clamp01(Math.max(a[1], b[1]))
  if (x1 - x0 < MIN_RECT_W || y1 - y0 < MIN_RECT_H) return null
  return [round5(x0), round5(y0), round5(x1 - x0), round5(y1 - y0)]
}

export function areaDraft(page: number, rect: Rect, color: MarkupColor): MarkDraft | null {
  const check = validateGeometry('area', { rect })
  return check.geometry ? { kind: 'area', page, geometry: check.geometry, color } : null
}

export function pinDraft(page: number, pt: [number, number], color: MarkupColor): MarkDraft | null {
  const check = validateGeometry('sticky', { pt })
  return check.geometry ? { kind: 'sticky', page, geometry: check.geometry, color } : null
}

export function bookmarkDraft(page: number, y: number, title = ''): MarkDraft | null {
  const check = validateGeometry('bookmark', { y })
  return check.geometry ? { kind: 'bookmark', page, geometry: check.geometry, comment: title } : null
}

/** A text box centred where the student tapped, kept inside the page. */
export function textBoxRect(at: [number, number], size: { w: number; h: number } = TEXT_BOX): Rect {
  const x = Math.min(Math.max(0, at[0] - size.w / 2), 1 - size.w)
  const y = Math.min(Math.max(0, at[1] - size.h / 2), 1 - size.h)
  return [round5(x), round5(y), round5(size.w), round5(size.h)]
}

export function textBoxDraft(
  page: number,
  rect: Rect,
  color: InkColor = 'i1',
  fs: number = TEXT_BOX.fs,
  text = '',
): MarkDraft | null {
  const check = validateGeometry('textbox', { rect, fs })
  return check.geometry ? { kind: 'textbox', page, geometry: check.geometry, color, comment: text } : null
}

export const clampFontSize = (fs: number) => round5(Math.min(MAX_FONT, Math.max(MIN_FONT, fs)))

/** Moves or resizes a rectangle inside the page, keeping it at least the minimum size. */
export function moveRect(rect: Rect, dx: number, dy: number): Rect {
  const x = Math.min(Math.max(0, rect[0] + dx), 1 - rect[2])
  const y = Math.min(Math.max(0, rect[1] + dy), 1 - rect[3])
  return [round5(x), round5(y), rect[2], rect[3]]
}
export function resizeRect(rect: Rect, dw: number, dh: number): Rect {
  const w = Math.min(Math.max(MIN_RECT_W, rect[2] + dw), 1 - rect[0])
  const h = Math.min(Math.max(MIN_RECT_H, rect[3] + dh), 1 - rect[1])
  return [rect[0], rect[1], round5(w), round5(h)]
}

export function inkDraft(page: number, strokes: Stroke[], color: InkColor): MarkDraft | null {
  const fitted = strokes.map((s) => ({ pts: s.pts, w: Math.min(MAX_STROKE_W, Math.max(MIN_STROKE_W, s.w)) }))
  const check = validateGeometry('ink', { strokes: fitted, bbox: inkBbox(fitted) })
  return check.geometry ? { kind: 'ink', page, geometry: check.geometry, color } : null
}

export type { ColorKey }
