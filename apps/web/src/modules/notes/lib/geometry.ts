/**
 * Geometry v1 (ERD 3.5), the TypeScript twin of `apps/api/modules/notes/domain/geometry.py`. The client validates before it
 * queues a write offline; the server validates again. Both read `geometry_cases.json`, so a rule changes in both or the
 * tests fail. Frame: the page as displayed with its intrinsic rotation, origin top-left, fractions of width and height,
 * five decimals (`round5`, half up on the decimal value: `Math.round` and Python's `round` would disagree).
 */

export type MarkKind = 'highlight' | 'underline' | 'area' | 'ink' | 'textbox' | 'sticky' | 'bookmark'
export type Rect = [number, number, number, number]
export interface Stroke {
  pts: [number, number][]
  w: number
}
export type Geometry =
  | { quads: Rect[] }
  | { rect: Rect; fs?: number }
  | { strokes: Stroke[]; bbox: Rect }
  | { pt: [number, number] }
  | { y: number }

export const ERROR_CODES = [
  'bad_kind',
  'bad_shape',
  'out_of_range',
  'too_many_quads',
  'quad_too_small',
  'rect_too_small',
  'too_many_strokes',
  'too_many_points',
  'too_large',
  'bad_width',
  'bad_font_size',
] as const
export type GeometryErrorCode = (typeof ERROR_CODES)[number]
export interface GeometryError {
  code: GeometryErrorCode
  message: string
}
export interface GeometryCheck {
  geometry: Geometry | null
  errors: GeometryError[]
}

export const MAX_QUADS = 200
export const MIN_QUAD_W = 0.002
export const MIN_QUAD_H = 0.004
export const MIN_RECT_W = 0.004
export const MIN_RECT_H = 0.004
export const MAX_STROKES = 50
export const MAX_POINTS = 20_000
export const MIN_STROKE_W = 0.001
export const MAX_STROKE_W = 0.02
export const MIN_FONT = 0.008
export const MAX_FONT = 0.06
export const MAX_BYTES = 64 * 1024
export const MERGE_GAP = 0.005
export const MERGE_LINE_OVERLAP = 0.5
const EPS = 1e-9

export const round5 = (x: number) => Math.floor(x * 100_000 + 0.5) / 100_000

const isNum = (v: unknown): v is number => typeof v === 'number' && Number.isFinite(v)
const isSeq = (v: unknown, n?: number): v is unknown[] => Array.isArray(v) && (n === undefined || v.length === n)
const unit = (v: unknown) => isNum(v) && v >= -EPS && v <= 1 + EPS
const isObj = (v: unknown): v is Record<string, unknown> => typeof v === 'object' && v !== null && !Array.isArray(v)

class Errors {
  items: GeometryError[] = []
  add(code: GeometryErrorCode, message: string) {
    if (this.items.every((e) => e.code !== code)) this.items.push({ code, message })
  }
}

function rectOf(value: unknown, errs: Errors, minW: number, minH: number, small: GeometryErrorCode): Rect | null {
  if (!(isSeq(value, 4) && value.every(isNum))) {
    errs.add('bad_shape', 'A rectangle is [x, y, w, h] with four numbers.')
    return null
  }
  const [x, y, w, h] = value as Rect
  if (!value.every(unit) || x + w > 1 + EPS || y + h > 1 + EPS) {
    errs.add('out_of_range', 'The rectangle must lie inside the page (0 to 1).')
    return null
  }
  if (w < minW || h < minH) {
    errs.add(small, 'The rectangle is too small.')
    return null
  }
  const rx = round5(x)
  const ry = round5(y)
  return [rx, ry, Math.min(round5(w), round5(1 - rx)), Math.min(round5(h), round5(1 - ry))]
}

function mergeable(a: Rect, b: Rect): boolean {
  const overlap = Math.min(a[1] + a[3], b[1] + b[3]) - Math.max(a[1], b[1])
  const gap = Math.max(a[0], b[0]) - Math.min(a[0] + a[2], b[0] + b[2])
  return overlap >= MERGE_LINE_OVERLAP * Math.min(a[3], b[3]) && gap <= MERGE_GAP
}

function union(a: Rect, b: Rect): Rect {
  const x = Math.min(a[0], b[0])
  const y = Math.min(a[1], b[1])
  return [x, y, Math.max(a[0] + a[2], b[0] + b[2]) - x, Math.max(a[1] + a[3], b[1] + b[3]) - y]
}

/** Merge quads on the same line that touch (gap of at most one word space). Same algorithm and order as the server. */
export function mergeAdjacentQuads(quads: Rect[]): Rect[] {
  const out = quads.map((q) => [...q] as Rect)
  let merged = true
  while (merged) {
    merged = false
    for (let i = 0; i < out.length && !merged; i++) {
      for (let j = i + 1; j < out.length; j++) {
        if (mergeable(out[i] as Rect, out[j] as Rect)) {
          out[i] = union(out[i] as Rect, out[j] as Rect)
          out.splice(j, 1)
          merged = true
          break
        }
      }
    }
  }
  return out.map((q) => q.map(round5) as Rect)
}

function quadsOf(g: Record<string, unknown>, errs: Errors): Geometry | null {
  const quads = g.quads
  if (!isSeq(quads) || quads.length === 0) {
    errs.add('bad_shape', '`quads` must be a non-empty list.')
    return null
  }
  if (quads.length > MAX_QUADS) {
    errs.add('too_many_quads', `At most ${MAX_QUADS} rectangles.`)
    return null
  }
  const rects = quads.map((q) => rectOf(q, errs, MIN_QUAD_W, MIN_QUAD_H, 'quad_too_small'))
  if (rects.some((r) => r === null)) return null
  return { quads: mergeAdjacentQuads(rects as Rect[]) }
}

/** Box around all points, grown by half the widest stroke and clamped to the page. */
export function inkBbox(strokes: Stroke[]): Rect {
  const xs = strokes.flatMap((s) => s.pts.map((p) => p[0]))
  const ys = strokes.flatMap((s) => s.pts.map((p) => p[1]))
  const pad = Math.max(...strokes.map((s) => s.w)) / 2
  const x0 = Math.max(0, Math.min(...xs) - pad)
  const y0 = Math.max(0, Math.min(...ys) - pad)
  const x1 = Math.min(1, Math.max(...xs) + pad)
  const y1 = Math.min(1, Math.max(...ys) + pad)
  return [round5(x0), round5(y0), round5(x1 - x0), round5(y1 - y0)]
}

function inkOf(g: Record<string, unknown>, errs: Errors): Geometry | null {
  const strokes = g.strokes
  if (!isSeq(strokes) || strokes.length === 0) {
    errs.add('bad_shape', '`strokes` must be a non-empty list.')
    return null
  }
  if (strokes.length > MAX_STROKES) {
    errs.add('too_many_strokes', `At most ${MAX_STROKES} strokes.`)
    return null
  }
  const shaped = strokes as Record<string, unknown>[]
  if (!shaped.every((s) => isObj(s) && isSeq(s.pts) && s.pts.length > 0)) {
    errs.add('bad_shape', 'A stroke is {pts: [[x, y], ...], w}.')
    return null
  }
  if (shaped.reduce((n, s) => n + (s.pts as unknown[]).length, 0) > MAX_POINTS) {
    errs.add('too_many_points', `At most ${MAX_POINTS} points.`)
    return null
  }
  const out: Stroke[] = []
  for (const s of shaped) {
    const w = s.w
    if (!isNum(w) || !(w >= MIN_STROKE_W && w <= MAX_STROKE_W)) {
      errs.add('bad_width', `Stroke width is ${MIN_STROKE_W} to ${MAX_STROKE_W}.`)
      return null
    }
    const pts = s.pts as unknown[]
    if (!pts.every((p) => isSeq(p, 2) && p.every(isNum))) {
      errs.add('bad_shape', 'A point is [x, y].')
      return null
    }
    if (!pts.every((p) => (p as number[]).every(unit))) {
      errs.add('out_of_range', 'Points must lie inside the page (0 to 1).')
      return null
    }
    out.push({
      pts: pts.map((p) => [round5((p as number[])[0] as number), round5((p as number[])[1] as number)]),
      w: round5(w),
    })
  }
  const result = { strokes: out, bbox: inkBbox(out) }
  if (serialisedSize(result) > MAX_BYTES) {
    errs.add('too_large', 'The drawing is too large; split it.')
    return null
  }
  return result
}

function textboxOf(g: Record<string, unknown>, errs: Errors): Geometry | null {
  const rect = rectOf(g.rect, errs, MIN_RECT_W, MIN_RECT_H, 'rect_too_small')
  const fs = g.fs
  if (!isNum(fs) || !(fs >= MIN_FONT && fs <= MAX_FONT)) {
    errs.add('bad_font_size', `Font size is ${MIN_FONT} to ${MAX_FONT} of the page height.`)
    return null
  }
  return rect === null ? null : { rect, fs: round5(fs) }
}

function areaOf(g: Record<string, unknown>, errs: Errors): Geometry | null {
  const rect = rectOf(g.rect, errs, MIN_RECT_W, MIN_RECT_H, 'rect_too_small')
  return rect === null ? null : { rect }
}

function stickyOf(g: Record<string, unknown>, errs: Errors): Geometry | null {
  const pt = g.pt
  if (!(isSeq(pt, 2) && pt.every(isNum))) {
    errs.add('bad_shape', '`pt` is [x, y].')
    return null
  }
  if (!pt.every(unit)) {
    errs.add('out_of_range', 'The point must lie inside the page (0 to 1).')
    return null
  }
  return { pt: [round5(pt[0] as number), round5(pt[1] as number)] }
}

function bookmarkOf(g: Record<string, unknown>, errs: Errors): Geometry | null {
  if (!isNum(g.y)) {
    errs.add('bad_shape', '`y` is a number.')
    return null
  }
  if (!unit(g.y)) {
    errs.add('out_of_range', '`y` must be between 0 and 1.')
    return null
  }
  return { y: round5(g.y) }
}

type Validator = (g: Record<string, unknown>, errs: Errors) => Geometry | null
const VALIDATORS: Record<MarkKind, Validator> = {
  highlight: quadsOf,
  underline: quadsOf,
  ink: inkOf,
  textbox: textboxOf,
  area: areaOf,
  sticky: stickyOf,
  bookmark: bookmarkOf,
}

/** Validate and normalise `geometry` for `kind`. `geometry` is null whenever `errors` is not empty. */
export function validateGeometry(kind: string, geometry: unknown): GeometryCheck {
  const errs = new Errors()
  const validator = Object.hasOwn(VALIDATORS, kind) ? VALIDATORS[kind as MarkKind] : undefined
  if (!validator) errs.add('bad_kind', 'Unknown mark kind.')
  else if (!isObj(geometry)) errs.add('bad_shape', 'Geometry must be an object.')
  else {
    const normalised = validator(geometry, errs)
    if (normalised !== null && errs.items.length === 0) return { geometry: normalised, errors: [] }
  }
  return { geometry: null, errors: errs.items }
}

const numberText = (n: number) => n.toFixed(5).replace(/0+$/, '').replace(/\.$/, '') || '0'

/** Length of the value as Postgres prints jsonb (what the server's size check measures); see the Python twin. */
export function serialisedSize(value: unknown): number {
  if (Array.isArray(value)) {
    const parts = value.map(serialisedSize)
    return 2 + parts.reduce((a, b) => a + b, 0) + 2 * Math.max(parts.length - 1, 0)
  }
  if (isObj(value)) {
    const parts = Object.entries(value).map(([k, v]) => k.length + 4 + serialisedSize(v))
    return 2 + parts.reduce((a, b) => a + b, 0) + 2 * Math.max(parts.length - 1, 0)
  }
  if (typeof value === 'string') return value.length + 2
  return numberText(value as number).length
}

/** Bounding box `[x, y, w, h]` of a normalised geometry. */
export function geometryBbox(kind: MarkKind, geometry: Geometry): Rect {
  if (kind === 'highlight' || kind === 'underline') {
    const quads = (geometry as { quads: Rect[] }).quads
    return quads
      .slice(1)
      .reduce(union, quads[0] as Rect)
      .map(round5) as Rect
  }
  if (kind === 'ink') return [...(geometry as { bbox: Rect }).bbox]
  if (kind === 'area' || kind === 'textbox') return [...(geometry as { rect: Rect }).rect]
  if (kind === 'sticky') {
    const pt = (geometry as { pt: [number, number] }).pt
    return [pt[0], pt[1], 0, 0]
  }
  return [0, (geometry as { y: number }).y, 1, 0]
}
