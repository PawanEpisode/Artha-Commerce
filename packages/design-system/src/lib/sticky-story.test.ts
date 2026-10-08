import { describe, expect, it } from 'vitest'

import { stepIndexFromProgress, stickyStepIndex, stickyStepScrollProgress } from './sticky-story'

describe('stepIndexFromProgress', () => {
  it('maps equal buckets from 0 inclusive to 1 exclusive of the last edge', () => {
    expect(stepIndexFromProgress(0, 11)).toBe(0)
    expect(stepIndexFromProgress(0.09, 11)).toBe(0)
    expect(stepIndexFromProgress(1 / 11, 11)).toBe(1)
    expect(stepIndexFromProgress(0.99, 11)).toBe(10)
    expect(stepIndexFromProgress(1, 11)).toBe(10)
  })

  it('clamps invalid progress and empty counts', () => {
    expect(stepIndexFromProgress(-1, 4)).toBe(0)
    expect(stepIndexFromProgress(2, 4)).toBe(3)
    expect(stepIndexFromProgress(Number.NaN, 4)).toBe(0)
    expect(stepIndexFromProgress(0.5, 1)).toBe(0)
    expect(stepIndexFromProgress(0.5, 0)).toBe(0)
  })
})

describe('stickyStepIndex', () => {
  it('holds the previous step near a boundary', () => {
    const bucket = 1 / 11
    expect(stickyStepIndex(bucket + 0.001, 11, 0)).toBe(0)
    expect(stickyStepIndex(bucket * 1.2, 11, 0)).toBe(1)
  })

  it('jumps more than one step without waiting', () => {
    expect(stickyStepIndex(0.9, 11, 0)).toBe(9)
  })
})

describe('stickyStepScrollProgress', () => {
  it('lands inside the target bucket', () => {
    expect(stepIndexFromProgress(stickyStepScrollProgress(0, 11), 11)).toBe(0)
    expect(stepIndexFromProgress(stickyStepScrollProgress(4, 11), 11)).toBe(4)
    expect(stepIndexFromProgress(stickyStepScrollProgress(10, 11), 11)).toBe(10)
  })
})
