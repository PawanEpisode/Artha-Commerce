import { describe, expect, it } from 'vitest'

import { filledSegments } from './progress'

describe('filledSegments', () => {
  it('lights arcs in proportion', () => {
    expect(filledSegments(0, 5)).toBe(0)
    expect(filledSegments(100, 5)).toBe(5)
    expect(filledSegments(60, 5)).toBe(3)
  })
  it('never hides a started ring and clamps the total to 1..12', () => {
    expect(filledSegments(1, 12)).toBe(1)
    expect(filledSegments(100, 40)).toBe(12)
    expect(filledSegments(50, 0)).toBe(1)
    expect(filledSegments(Number.NaN, 4)).toBe(0)
  })
})
