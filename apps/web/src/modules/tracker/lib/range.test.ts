import { describe, expect, it } from 'vitest'

import { defaultGroup, presetRange, rangeProblem } from './range'

describe('presetRange', () => {
  const today = '2026-10-08' // a Thursday
  it('ends every preset on today', () => {
    expect(presetRange('today', today)).toEqual({ from: today, to: today })
    expect(presetRange('7d', today)).toEqual({ from: '2026-10-02', to: today })
    expect(presetRange('30d', today)).toEqual({ from: '2026-09-09', to: today })
    expect(presetRange('90d', today).from).toBe('2026-07-11')
  })
  it('starts "this week" on the configured week start', () => {
    expect(presetRange('week', today, 1).from).toBe('2026-10-05')
    expect(presetRange('week', today, 0).from).toBe('2026-10-04')
  })
  it('keeps a custom range as given', () => {
    expect(presetRange('custom', today, 1, { from: '2026-01-01', to: '2026-01-31' })).toEqual({
      from: '2026-01-01',
      to: '2026-01-31',
    })
  })
})

describe('rangeProblem', () => {
  it('rejects a backwards range and one longer than five years', () => {
    expect(rangeProblem({ from: '2026-10-05', to: '2026-10-01' })).toMatch(/on or before/)
    expect(rangeProblem({ from: '2020-01-01', to: '2026-10-01' })).toMatch(/five years/)
    expect(rangeProblem({ from: '2026-09-01', to: '2026-10-01' })).toBeNull()
  })
})

describe('defaultGroup', () => {
  it('uses days, then weeks, then months as the range grows', () => {
    expect(defaultGroup({ from: '2026-09-09', to: '2026-10-08' })).toBe('day')
    expect(defaultGroup({ from: '2026-07-11', to: '2026-10-08' })).toBe('week')
    expect(defaultGroup({ from: '2024-01-01', to: '2026-10-08' })).toBe('month')
  })
})
