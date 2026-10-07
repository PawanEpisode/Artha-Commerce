/**
 * Turns the text runs an engine reports (position in the viewport at scale 1, in points) into `LayerItem`s in the
 * normalised frame, and builds the page text. Pure, so it is tested without a PDF. pdf.js specifics (its matrices) are
 * handled by the caller; this takes plain numbers.
 */
import type { LayerItem, PdfTextContent } from './index'

/** A run as drawn: baseline origin and rotation in page points (y down), width along the baseline, font size. */
export interface RawRun {
  str: string
  /** Baseline start, in points from the top-left of the displayed page. */
  x: number
  y: number
  /** Length of the run along the baseline, points. */
  width: number
  /** Font size, points. */
  fontSize: number
  /** Radians, clockwise on screen. */
  angle: number
  hasEOL: boolean
}

/** Share of the font size above the baseline: the top of the line box. */
export const ASCENT = 0.8

const r4 = (n: number) => Math.round(n * 10_000) / 10_000

export function buildTextModel(runs: ReadonlyArray<RawRun>, pageW: number, pageH: number): PdfTextContent {
  let text = ''
  const items: LayerItem[] = []
  for (const run of runs) {
    if (run.str.length > 0) {
      const sin = Math.sin(run.angle)
      const cos = Math.cos(run.angle)
      const left = run.x + ASCENT * run.fontSize * sin
      const top = run.y - ASCENT * run.fontSize * cos
      items.push({
        str: run.str,
        x: r4(left / pageW),
        y: r4(top / pageH),
        w: r4(run.width / pageW),
        h: r4(run.fontSize / pageH),
        angle: run.angle,
        start: text.length,
      })
      text += run.str
    }
    if (run.hasEOL && text.length > 0 && !text.endsWith('\n')) text += '\n'
  }
  return { text, items }
}

export const pageTextOf = (runs: ReadonlyArray<Pick<RawRun, 'str' | 'hasEOL'>>): string => {
  let text = ''
  for (const run of runs) {
    text += run.str
    if (run.hasEOL && text.length > 0 && !text.endsWith('\n')) text += '\n'
  }
  return text
}

/** Multiplies two 2D affine matrices `[a, b, c, d, e, f]` (pdf.js convention: `m1` applied after `m2`). */
export function multiply(m1: ReadonlyArray<number>, m2: ReadonlyArray<number>): number[] {
  const [a1 = 1, b1 = 0, c1 = 0, d1 = 1, e1 = 0, f1 = 0] = m1
  const [a2 = 1, b2 = 0, c2 = 0, d2 = 1, e2 = 0, f2 = 0] = m2
  return [
    a1 * a2 + c1 * b2,
    b1 * a2 + d1 * b2,
    a1 * c2 + c1 * d2,
    b1 * c2 + d1 * d2,
    a1 * e2 + c1 * f2 + e1,
    b1 * e2 + d1 * f2 + f1,
  ]
}

/**
 * One pdf.js text item to a `RawRun`. `viewportTransform` maps user space to the displayed page at scale 1 (it includes
 * the page's `/Rotate` and the y flip); `itemTransform` is the item's own text matrix.
 */
export function runFromPdfItem(
  item: { str: string; transform: number[]; width: number; hasEOL: boolean },
  viewportTransform: number[],
): RawRun {
  const m = multiply(viewportTransform, item.transform)
  const [a = 1, b = 0, c = 0, d = 1, e = 0, f = 0] = m
  return {
    str: item.str,
    x: e,
    y: f,
    width: item.width * Math.hypot(viewportTransform[0] ?? 1, viewportTransform[1] ?? 0),
    fontSize: Math.hypot(c, d),
    angle: Math.atan2(b, a),
    hasEOL: item.hasEOL,
  }
}
