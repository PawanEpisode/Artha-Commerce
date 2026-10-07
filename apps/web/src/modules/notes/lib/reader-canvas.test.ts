import { describe, expect, it } from 'vitest'

import { MAX_CANVAS_PIXELS, planCanvas } from './reader-canvas'

describe('planCanvas', () => {
  it('uses the screen pixel ratio up to two', () => {
    const plan = planCanvas(595, 842, 0.6, 3)
    expect(plan.renderScale).toBeCloseTo(1.2)
    expect(plan.clamped).toBe(false)
    expect(plan.width).toBe(Math.floor(595 * 1.2))
  })

  it('lowers the scale until the canvas fits the pixel cap', () => {
    const plan = planCanvas(595, 842, 5, 2)
    expect(plan.clamped).toBe(true)
    expect(plan.width * plan.height).toBeLessThanOrEqual(MAX_CANVAS_PIXELS)
    expect(plan.width * plan.height).toBeGreaterThan(MAX_CANVAS_PIXELS * 0.97)
  })

  it('draws a quick draft at about a quarter of the pixels', () => {
    const full = planCanvas(595, 842, 1, 2)
    const draft = planCanvas(595, 842, 1, 2, { draft: true })
    expect(draft.width * draft.height).toBeLessThan(full.width * full.height * 0.3)
  })

  it('never makes an empty canvas', () => {
    const plan = planCanvas(1, 1, 0.01, 1)
    expect(plan.width).toBeGreaterThanOrEqual(1)
    expect(plan.height).toBeGreaterThanOrEqual(1)
  })
})
