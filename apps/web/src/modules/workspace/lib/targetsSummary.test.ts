import { describe, expect, it } from 'vitest'

import { targetRows, targetsHeading } from './targetsSummary'

describe('targetRows', () => {
  it('pluralises and keeps counts', () => {
    expect(targetRows({ practice_sets: 2, revisions: 1, mocks: 3 })).toEqual([
      { label: 'practice sets', count: 2 },
      { label: 'revision', count: 1 },
      { label: 'mocks', count: 3 },
    ])
  })

  it('marks an untracked activity with null instead of zero', () => {
    expect(targetRows({ practice_sets: 0, revisions: 2, mocks: 0 }).map((r) => r.count)).toEqual([null, 2, null])
  })
})

describe('targetsHeading', () => {
  it('names the preset, or Custom', () => {
    expect(targetsHeading('standard')).toBe('Standard targets')
    expect(targetsHeading('custom')).toBe('Custom targets')
  })
})
