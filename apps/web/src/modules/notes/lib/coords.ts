/**
 * Coordinate maths for marks on a PDF page, the TypeScript twin of `apps/api/modules/notes/domain/coords.py` (shared
 * `coords_cases.json`). Stored frame: the page as displayed with its intrinsic `/Rotate`, origin top-left, fractions of
 * width and height. Viewed frame: the stored frame turned by the student's rotation (clockwise, 0/90/180/270) and scaled by
 * the zoom. Only the stored frame ever leaves the browser.
 */
import { type Rect, round5 } from './geometry'

export type Rotation = 0 | 90 | 180 | 270
export type Point = [number, number]

/** 0, 90, 180 or 270 for any multiple of 90 (negatives and 360+ wrap); anything else throws. */
export function normaliseRotation(degrees: number): Rotation {
  if (!Number.isInteger(degrees) || degrees % 90 !== 0)
    throw new RangeError(`rotation must be a multiple of 90, got ${degrees}`)
  return (((degrees % 360) + 360) % 360) as Rotation
}

/** Width and height of the page as viewed: swapped at 90 and 270. */
export function viewSize(pageW: number, pageH: number, rotation: number): [number, number] {
  const r = normaliseRotation(rotation)
  return r === 90 || r === 270 ? [pageH, pageW] : [pageW, pageH]
}

/** A rectangle in points (page as displayed) to the stored frame: 119, 168.4, 238, 13.4 on 595 x 842 is [0.2, 0.2, 0.4, 0.01591]. */
export const normaliseRect = (x: number, y: number, w: number, h: number, pageW: number, pageH: number): Rect => [
  round5(x / pageW),
  round5(y / pageH),
  round5(w / pageW),
  round5(h / pageH),
]

export const denormaliseRect = (rect: Rect, pageW: number, pageH: number): Rect => [
  rect[0] * pageW,
  rect[1] * pageH,
  rect[2] * pageW,
  rect[3] * pageH,
]

/** Stored point to the viewed frame; a clockwise quarter turn sends the top-left corner to the top-right: (x, y) -> (1 - y, x). */
export function rotatePoint([x, y]: Point, rotation: number): Point {
  const r = normaliseRotation(rotation)
  if (r === 90) return [round5(1 - y), round5(x)]
  if (r === 180) return [round5(1 - x), round5(1 - y)]
  if (r === 270) return [round5(y), round5(1 - x)]
  return [round5(x), round5(y)]
}

/** Stored rectangle to the viewed frame (width and height swap at 90 and 270), rounded like stored values. */
export function rotateRect([x, y, w, h]: Rect, rotation: number): Rect {
  const r = normaliseRotation(rotation)
  if (r === 90) return [round5(1 - y - h), round5(x), round5(h), round5(w)]
  if (r === 180) return [round5(1 - x - w), round5(1 - y - h), round5(w), round5(h)]
  if (r === 270) return [round5(y), round5(1 - x - w), round5(h), round5(w)]
  return [round5(x), round5(y), round5(w), round5(h)]
}

export const unrotateRect = (rect: Rect, rotation: number): Rect => rotateRect(rect, -normaliseRotation(rotation))
export const unrotatePoint = (pt: Point, rotation: number): Point => rotatePoint(pt, -normaliseRotation(rotation))

/** Size in CSS pixels of the page on screen. `zoom` is CSS pixels per PDF point (1 = 72 dpi at 100%). */
export function viewportSize(
  pageW: number,
  pageH: number,
  zoom: number,
  rotation: number,
): { width: number; height: number } {
  const [w, h] = viewSize(pageW, pageH, rotation)
  return { width: w * zoom, height: h * zoom }
}

export interface Viewport {
  width: number
  height: number
  rotation: number
}

/** Stored rectangle to pixels inside the page element (origin at its top-left corner). */
export function toViewportRect(rect: Rect, view: Viewport): Rect {
  const [x, y, w, h] = rotateRect(rect, view.rotation)
  return [x * view.width, y * view.height, w * view.width, h * view.height]
}

/** Pixels inside the page element (a drag, a tap) back to the stored frame, rounded to five decimals. */
export function fromViewportRect([x, y, w, h]: Rect, view: Viewport): Rect {
  return unrotateRect([x / view.width, y / view.height, w / view.width, h / view.height], view.rotation)
}

export const toViewportPoint = ([x, y]: Point, view: Viewport): Point => {
  const [rx, ry] = rotatePoint([x, y], view.rotation)
  return [rx * view.width, ry * view.height]
}

export const fromViewportPoint = ([x, y]: Point, view: Viewport): Point =>
  unrotatePoint([x / view.width, y / view.height], view.rotation)
