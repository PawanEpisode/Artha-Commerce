import { describe, expect, it } from 'vitest'

import {
  clampPercent,
  doubleTapZoom,
  formatStoredZoom,
  parseStoredZoom,
  percentFor,
  pinchPercent,
  scaleFor,
  stepZoom,
  zoomLabel,
} from './reader-zoom'

describe('stored zoom', () => {
  it('reads fit and percents, and treats anything else as fit', () => {
    expect(parseStoredZoom('fit')).toBe('fit')
    expect(parseStoredZoom('125')).toBe(125)
    expect(parseStoredZoom('125.4')).toBe(125)
    expect(parseStoredZoom('5')).toBe('fit')
    expect(parseStoredZoom('9000')).toBe('fit')
    expect(parseStoredZoom('abc')).toBe('fit')
    expect(parseStoredZoom(null)).toBe('fit')
  })

  it('writes what the API stores', () => {
    expect(formatStoredZoom('fit')).toBe('fit')
    expect(formatStoredZoom(150)).toBe('150')
    expect(formatStoredZoom(9999)).toBe('500')
  })
})

describe('scaleFor', () => {
  it('fits the page to the width', () => {
    expect(scaleFor('fit', 344, 595)).toBeCloseTo(344 / 595)
    expect(percentFor('fit', 344, 595)).toBe(58)
  })

  it('does not blow up a tiny page at fit width', () => {
    expect(scaleFor('fit', 1000, 50)).toBe(3)
  })

  it('uses the percent as pixels per point', () => {
    expect(scaleFor(100, 344, 595)).toBe(1)
    expect(scaleFor(250, 344, 595)).toBe(2.5)
    expect(scaleFor(1000, 344, 595)).toBe(5)
  })
})

describe('steps and gestures', () => {
  it('steps through the ladder from any percent', () => {
    expect(stepZoom(58, 1)).toBe(75)
    expect(stepZoom(100, 1)).toBe(125)
    expect(stepZoom(100, -1)).toBe(75)
    expect(stepZoom(58, -1)).toBe(50)
    expect(stepZoom(500, 1)).toBe(500)
    expect(stepZoom(25, -1)).toBe(25)
  })

  it('clamps a pinch', () => {
    expect(pinchPercent(100, 1.5)).toBe(150)
    expect(pinchPercent(100, 100)).toBe(500)
    expect(pinchPercent(100, 0.01)).toBe(25)
    expect(clampPercent(24.6)).toBe(25)
  })

  it('double tap goes to twice fit, and back to fit when already magnified', () => {
    expect(doubleTapZoom('fit', 58)).toBe(150)
    expect(doubleTapZoom('fit', 100)).toBe(200)
    expect(doubleTapZoom(200, 58)).toBe('fit')
    expect(doubleTapZoom(60, 58)).toBe(150)
  })

  it('labels', () => {
    expect(zoomLabel(57.6)).toBe('58%')
  })
})
