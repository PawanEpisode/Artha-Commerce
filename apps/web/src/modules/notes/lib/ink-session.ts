/**
 * The pen's drawings, as data: a finished stroke becomes a simplified stroke in the stored frame; strokes within two
 * seconds of each other on one page and one colour join into one annotation (one drawing per burst, ERD 3.5), and the
 * last stroke can be undone and redone. Pure; the container turns the result into mark writes.
 */
import type { InkColor } from './annotation-types'
import { inkBbox, MAX_STROKES, round5, type Stroke } from './geometry'
import { BURST_GAP_MS, limitPoints, type Point, simplifyStroke, type TimedStroke } from './simplify'

export interface TimedPoint {
  /** Stored frame, x and y in [0, 1]. */
  x: number
  y: number
  t: number
}

/** A raw stroke (every sampled point) to a simplified one. Width is a fraction of the page width. */
export function finishStroke(points: readonly TimedPoint[], width: number): TimedStroke | null {
  const first = points[0]
  const last = points[points.length - 1]
  if (!first || !last) return null
  const pts = points.map((p): Point => [round5(Math.min(1, Math.max(0, p.x))), round5(Math.min(1, Math.max(0, p.y)))])
  // A tap with the pen is a dot: one point drawn with a round cap.
  const stroke: TimedStroke = { pts, w: width, t0: first.t, t1: last.t }
  return simplifyStroke(stroke)
}

export interface InkDrawing {
  markId: string
  page: number
  color: InkColor
  strokes: TimedStroke[]
  /** Strokes taken back with undo, newest last, for redo. */
  redo: TimedStroke[]
}

const lastEnd = (d: InkDrawing) => d.strokes.reduce((n, s) => Math.max(n, s.t1 ?? s.t0), 0)

/** A stroke joins the drawing in progress when it is on the same page and colour, starts within the burst gap and there is room. */
export function joinsDrawing(current: InkDrawing | null, page: number, color: InkColor, stroke: TimedStroke): boolean {
  return (
    current !== null &&
    current.page === page &&
    current.color === color &&
    current.strokes.length < MAX_STROKES &&
    stroke.t0 - lastEnd(current) <= BURST_GAP_MS
  )
}

export function addStroke(
  current: InkDrawing | null,
  next: { page: number; color: InkColor; stroke: TimedStroke; newId: () => string },
): { drawing: InkDrawing; created: boolean } {
  if (current && joinsDrawing(current, next.page, next.color, next.stroke))
    return { drawing: { ...current, strokes: [...current.strokes, next.stroke], redo: [] }, created: false }
  return {
    drawing: { markId: next.newId(), page: next.page, color: next.color, strokes: [next.stroke], redo: [] },
    created: true,
  }
}

/** Takes the newest stroke back. When `drawing.strokes` is empty the annotation should be deleted (redo can bring it back). */
export function undoStroke(drawing: InkDrawing): { drawing: InkDrawing; removed: TimedStroke | null } {
  const removed = drawing.strokes[drawing.strokes.length - 1] ?? null
  if (!removed) return { drawing, removed: null }
  const strokes = drawing.strokes.slice(0, -1)
  const redo = [...drawing.redo, removed]
  return { drawing: { ...drawing, strokes, redo }, removed }
}

export function redoStroke(drawing: InkDrawing): InkDrawing {
  const stroke = drawing.redo[drawing.redo.length - 1]
  if (!stroke) return drawing
  return { ...drawing, strokes: [...drawing.strokes, stroke], redo: drawing.redo.slice(0, -1) }
}

/** The geometry v1 of a drawing: strokes within the 20,000 point limit and their box. */
export function inkGeometry(strokes: readonly TimedStroke[]): {
  strokes: Stroke[]
  bbox: [number, number, number, number]
} {
  const kept = limitPoints(strokes.map(({ pts, w }) => ({ pts, w })))
  return { strokes: kept, bbox: inkBbox(kept) }
}
