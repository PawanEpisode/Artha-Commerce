import { describe, expect, it } from 'vitest'

import { formatLastSeen } from './format'

const NOW = new Date(2026, 9, 6, 15, 0, 0) // 6 Oct 2026, local time

describe('formatLastSeen', () => {
  it('speaks in days for the last week', () => {
    expect(formatLastSeen(new Date(2026, 9, 6, 1, 0).toISOString(), NOW)).toBe('Last used today')
    expect(formatLastSeen(new Date(2026, 9, 5, 23, 0).toISOString(), NOW)).toBe('Last used yesterday')
    expect(formatLastSeen(new Date(2026, 9, 3, 12, 0).toISOString(), NOW)).toBe('Last used 3 days ago')
  })

  it('gives the date after a week', () => {
    expect(formatLastSeen(new Date(2026, 8, 20, 12, 0).toISOString(), NOW)).toBe('Last used 20 Sept')
  })

  it('handles a missing or broken time', () => {
    expect(formatLastSeen(null, NOW)).toBe('Not used yet')
    expect(formatLastSeen(undefined, NOW)).toBe('Not used yet')
    expect(formatLastSeen('not a date', NOW)).toBe('Not used yet')
  })
})
