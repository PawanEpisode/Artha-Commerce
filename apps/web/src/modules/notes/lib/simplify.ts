/**
 * Ink simplification, the TypeScript twin of `apps/api/modules/notes/domain/simplify.py` (shared `simplify_cases.json`):
 * Ramer-Douglas-Peucker with a 0.0005 tolerance, drawing bursts of strokes within 2 s, and a guard that keeps a drawing
 * under the 20,000 point limit. The pen layer simplifies on pointer up, so a stored drawing is small and an offline
 * queue stays cheap. Read the Python module docstring for the reasoning.
 */
import { MAX_POINTS, MAX_STROKES } from './geometry'

export const DEFAULT_TOLERANCE = 0.0005
export const BURST_GAP_MS = 2000
const MAX_DOUBLINGS = 8

export type Point = [number, number]
export interface InkStroke {
  pts: Point[]
  w: number
}
export interface TimedStroke extends InkStroke {
  t0: number
  t1?: number
}

function distance(p: Point, a: Point, b: Point): number {
  const dx = b[0] - a[0]
  const dy = b[1] - a[1]
  const length2 = dx * dx + dy * dy
  if (length2 === 0) return Math.sqrt((p[0] - a[0]) ** 2 + (p[1] - a[1]) ** 2)
  return Math.abs(dx * (a[1] - p[1]) - (a[0] - p[0]) * dy) / Math.sqrt(length2)
}

/** Ramer-Douglas-Peucker, iterative. Returns a new array holding a subset of the input points, ends included. */
export function simplifyPoints(pts: Point[], tolerance = DEFAULT_TOLERANCE): Point[] {
  const n = pts.length
  if (n <= 2) return pts.map((p) => [...p] as Point)
  const keep = new Array<boolean>(n).fill(false)
  keep[0] = true
  keep[n - 1] = true
  const stack: [number, number][] = [[0, n - 1]]
  for (let top = stack.pop(); top; top = stack.pop()) {
    const [lo, hi] = top
    if (hi - lo < 2) continue
    let far = -1
    let farD = 0
    for (let i = lo + 1; i < hi; i++) {
      const d = distance(pts[i] as Point, pts[lo] as Point, pts[hi] as Point)
      if (d > farD) {
        far = i
        farD = d
      }
    }
    if (farD > tolerance) {
      keep[far] = true
      stack.push([lo, far], [far, hi])
    }
  }
  return pts.filter((_, i) => keep[i]).map((p) => [...p] as Point)
}

export const simplifyStroke = <T extends InkStroke>(stroke: T, tolerance = DEFAULT_TOLERANCE): T => ({
  ...stroke,
  pts: simplifyPoints(stroke.pts, tolerance),
})

/** Group strokes (milliseconds) into drawings: a stroke joins when it starts within `gapMs` of the latest end and there is room. */
export function groupBursts<T extends TimedStroke>(
  strokes: T[],
  gapMs = BURST_GAP_MS,
  maxStrokes = MAX_STROKES,
): T[][] {
  const ordered = [...strokes].sort((a, b) => a.t0 - b.t0) // Array.prototype.sort is stable
  const groups: T[][] = []
  let latestEnd = 0
  for (const s of ordered) {
    const last = groups[groups.length - 1]
    if (last && s.t0 - latestEnd <= gapMs && last.length < maxStrokes) {
      last.push(s)
      latestEnd = Math.max(latestEnd, s.t1 ?? s.t0)
    } else {
      groups.push([s])
      latestEnd = s.t1 ?? s.t0
    }
  }
  return groups
}

const evenly = (pts: Point[], keep: number): Point[] =>
  Array.from({ length: keep }, (_, i) => [...(pts[Math.floor((i * (pts.length - 1)) / (keep - 1))] as Point)] as Point)

const total = (strokes: InkStroke[]) => strokes.reduce((n, s) => n + s.pts.length, 0)

/** Strokes whose points total at most `maxPoints`: simplify harder (tolerance doubles), then thin evenly. Within the limit while it allows two points per stroke. */
export function limitPoints<T extends InkStroke>(
  strokes: T[],
  maxPoints = MAX_POINTS,
  tolerance = DEFAULT_TOLERANCE,
): T[] {
  const all = total(strokes)
  if (all <= maxPoints) return strokes.map((s) => ({ ...s, pts: s.pts.map((p) => [...p] as Point) }))
  let tol = tolerance
  for (let i = 0; i < MAX_DOUBLINGS; i++) {
    tol *= 2
    const out = strokes.map((s) => simplifyStroke(s, tol))
    if (total(out) <= maxPoints) return out
  }
  return strokes.map((s) => {
    const share = Math.max(2, Math.floor((maxPoints * s.pts.length) / all))
    return { ...s, pts: s.pts.length > share ? evenly(s.pts, share) : s.pts.map((p) => [...p] as Point) }
  })
}
