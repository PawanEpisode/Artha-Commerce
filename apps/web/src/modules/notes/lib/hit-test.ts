import type { MarkRecord } from './annotation-types'
import type { Rect } from './geometry'

type Hittable = Pick<MarkRecord, 'id' | 'kind' | 'page' | 'geometry' | 'deleted_at' | 'created_at'>
export type Pt = [number, number]

const inside = (rect: Rect, [x, y]: Pt, [tx, ty]: Pt) =>
  x >= rect[0] - tx && x <= rect[0] + rect[2] + tx && y >= rect[1] - ty && y <= rect[1] + rect[3] + ty

function segmentDistance(p: Pt, a: Pt, b: Pt, scale: Pt): number {
  const [px, py] = [p[0] * scale[0], p[1] * scale[1]]
  const [ax, ay] = [a[0] * scale[0], a[1] * scale[1]]
  const [bx, by] = [b[0] * scale[0], b[1] * scale[1]]
  const dx = bx - ax
  const dy = by - ay
  const len2 = dx * dx + dy * dy
  const t = len2 === 0 ? 0 : Math.max(0, Math.min(1, ((px - ax) * dx + (py - ay) * dy) / len2))
  return Math.hypot(px - (ax + t * dx), py - (ay + t * dy))
}

/** Pins and flags are small targets with a fixed reach in pixels; the caller passes the tolerance as page fractions. */
function hits(mark: Hittable, p: Pt, tol: Pt): boolean {
  const g = mark.geometry
  switch (mark.kind) {
    case 'highlight':
    case 'underline':
      return (g as { quads: Rect[] }).quads.some((q) => inside(q, p, [0, 0]))
    case 'area':
    case 'textbox':
      return inside((g as { rect: Rect }).rect, p, [0, 0])
    case 'sticky': {
      const pt = (g as { pt: Pt }).pt
      return Math.abs(pt[0] - p[0]) <= tol[0] * 1.5 && Math.abs(pt[1] - p[1]) <= tol[1] * 1.5
    }
    case 'bookmark':
      return p[0] <= tol[0] * 3 && Math.abs((g as { y: number }).y - p[1]) <= tol[1] * 1.5
    case 'ink': {
      const { strokes, bbox } = g as { strokes: Array<{ pts: Pt[]; w: number }>; bbox: Rect }
      if (!inside(bbox, p, tol)) return false
      // Measured in units of the tolerance (about a finger's reach), so a stroke is as easy to hit across a tall page.
      const scale: Pt = [1 / Math.max(tol[0], 1e-9), 1 / Math.max(tol[1], 1e-9)]
      return strokes.some((s) => {
        const reach = Math.max(1, s.w / 2 / Math.max(tol[0], 1e-9))
        if (s.pts.length === 1) return segmentDistance(p, s.pts[0] as Pt, s.pts[0] as Pt, scale) <= reach
        return s.pts.some((pt, i) => i > 0 && segmentDistance(p, s.pts[i - 1] as Pt, pt, scale) <= reach)
      })
    }
  }
}

/** Closer-to-the-top kinds win: a pin over a text box over a drawing over an area over text markup; newest first. */
const PRIORITY: Record<MarkRecord['kind'], number> = {
  sticky: 0,
  bookmark: 1,
  textbox: 2,
  ink: 3,
  area: 4,
  underline: 5,
  highlight: 6,
}

/**
 * The mark under a point of a page (stored frame), or null. `tol` is how far a finger or pointer reaches, as fractions
 * of the page width and height. Canvas marks are not focusable, so this is how a tap or a click selects one.
 */
export function hitTest(marks: readonly Hittable[], page: number, point: Pt, tol: Pt): Hittable | null {
  const found = marks.filter((m) => m.page === page && !m.deleted_at && hits(m, point, tol))
  found.sort((a, b) => PRIORITY[a.kind] - PRIORITY[b.kind] || b.created_at.localeCompare(a.created_at))
  return found[0] ?? null
}
