import { describe, expect, it } from 'vitest'

import { ageBucket, coverageBucket, lengthBucket, toastSampleRate } from './buckets'

describe('buckets', () => {
  it('groups name lengths', () => {
    expect([1, 10, 11, 20, 21, 40, 41, 80].map(lengthBucket)).toEqual([
      '1-10',
      '1-10',
      '11-20',
      '11-20',
      '21-40',
      '21-40',
      '41+',
      '41+',
    ])
  })
  it('groups coverage into tens and clamps', () => {
    expect([0, 9, 10, 49.9, 99, 100, 120, -5].map(coverageBucket)).toEqual([
      '0-9',
      '0-9',
      '10-19',
      '40-49',
      '90-99',
      '100',
      '100',
      '0-9',
    ])
  })
  it('groups ages', () => {
    expect([0, 3_599_999, 3_600_000, 86_400_000, 7 * 86_400_000].map(ageBucket)).toEqual([
      '<1h',
      '<1h',
      '<1d',
      '<7d',
      '7d+',
    ])
  })
  it('keeps every error and warning, samples the rest', () => {
    expect(toastSampleRate('error')).toBe(1)
    expect(toastSampleRate('warning')).toBe(1)
    expect(toastSampleRate('success')).toBe(0.1)
  })
})
