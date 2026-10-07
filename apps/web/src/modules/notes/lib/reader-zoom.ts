/**
 * Zoom maths of the reader. Zoom is `'fit'` (each page as wide as the reading area) or a percent: CSS pixels per PDF
 * point times 100, so 100 is one point per pixel (a 595 pt A4 page is 595 px wide). Pure, no DOM.
 */
import { MAX_ZOOM_PERCENT, MIN_ZOOM_PERCENT, type ZoomSpec } from './reader-schema'

export const ZOOM_STEPS = [25, 50, 75, 100, 125, 150, 200, 300, 400, 500] as const

export const clampPercent = (percent: number) =>
  Math.min(MAX_ZOOM_PERCENT, Math.max(MIN_ZOOM_PERCENT, Math.round(percent)))

/** The server stores `fit` or a percent as text; anything else reads as `fit`. */
export function parseStoredZoom(stored: string | null | undefined): ZoomSpec {
  if (!stored || stored === 'fit') return 'fit'
  const n = Number(stored)
  return Number.isFinite(n) && n >= MIN_ZOOM_PERCENT && n <= MAX_ZOOM_PERCENT ? Math.round(n) : 'fit'
}

export const formatStoredZoom = (zoom: ZoomSpec): string => (zoom === 'fit' ? 'fit' : String(clampPercent(zoom)))

/** CSS pixels per point for one page. Fit width never magnifies a page past 300%, so a tiny page does not blow up. */
export function scaleFor(zoom: ZoomSpec, availWidth: number, pageWidth: number): number {
  if (zoom === 'fit') return Math.min(3, Math.max(0.05, availWidth / Math.max(1, pageWidth)))
  return clampPercent(zoom) / 100
}

/** The percent the student sees for a page at this zoom. */
export const percentFor = (zoom: ZoomSpec, availWidth: number, pageWidth: number) =>
  Math.round(scaleFor(zoom, availWidth, pageWidth) * 100)

/** The next step up or down from the percent now shown. Moving past the ends stays at the end. */
export function stepZoom(currentPercent: number, direction: 1 | -1): number {
  const now = Math.round(currentPercent)
  if (direction === 1) return ZOOM_STEPS.find((s) => s > now) ?? MAX_ZOOM_PERCENT
  return [...ZOOM_STEPS].reverse().find((s) => s < now) ?? MIN_ZOOM_PERCENT
}

/** A pinch: the percent at the start of the gesture times the finger-distance ratio. */
export const pinchPercent = (startPercent: number, ratio: number) => clampPercent(startPercent * ratio)

/** Double tap: back to fit when already magnified, otherwise to twice fit (at least 150%). */
export function doubleTapZoom(zoom: ZoomSpec, fitPercent: number): ZoomSpec {
  if (zoom !== 'fit' && zoom > fitPercent * 1.15) return 'fit'
  return clampPercent(Math.max(150, fitPercent * 2))
}

/** Percent on screen for the reader's zoom control. */
export const zoomLabel = (percent: number) => `${Math.round(percent)}%`
