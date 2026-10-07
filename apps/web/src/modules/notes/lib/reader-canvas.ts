/** Canvas budget of one page: a pixel cap (iOS Safari refuses large canvases) and the device pixel ratio. */

export const MAX_CANVAS_PIXELS = 16_700_000
export const MAX_LIVE_CANVASES = 5
/** Above this the canvas gets no extra sharpness from the screen's pixel ratio: memory matters more than crispness. */
export const MAX_DPR = 2

export interface CanvasPlan {
  /** Backing-store size in device pixels. */
  width: number
  height: number
  /** Scale passed to the renderer: CSS scale times the pixel ratio actually used (at most `cssScale * MAX_DPR`). */
  renderScale: number
  /** True when the pixel cap forced a lower resolution than the screen could show. */
  clamped: boolean
}

/**
 * The canvas for a page of `pageW x pageH` points shown at `cssScale` CSS pixels per point. The render scale is lowered
 * until `width * height` fits `maxPixels`; the browser then stretches the canvas to the page box, so it stays correct
 * but softer. `draft` renders a quick low-resolution first pass (about a quarter of the pixels).
 */
export function planCanvas(
  pageW: number,
  pageH: number,
  cssScale: number,
  dpr: number,
  options: { maxPixels?: number; draft?: boolean } = {},
): CanvasPlan {
  const maxPixels = options.maxPixels ?? MAX_CANVAS_PIXELS
  const ratio = Math.min(MAX_DPR, Math.max(1, dpr)) * (options.draft ? 0.5 : 1)
  let renderScale = cssScale * ratio
  let width = Math.max(1, Math.floor(pageW * renderScale))
  let height = Math.max(1, Math.floor(pageH * renderScale))
  let clamped = false
  if (width * height > maxPixels) {
    renderScale *= Math.sqrt(maxPixels / (width * height))
    width = Math.max(1, Math.floor(pageW * renderScale))
    height = Math.max(1, Math.floor(pageH * renderScale))
    clamped = true
  }
  return { width, height, renderScale, clamped }
}
