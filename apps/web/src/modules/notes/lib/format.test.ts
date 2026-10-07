import { describe, expect, it } from 'vitest'

import { daysLeft, formatBytes, pluralize, relativeTime } from './format'

const NOW = new Date('2026-10-07T12:00:00Z').getTime()

describe('relativeTime', () => {
  it('speaks in minutes, hours and yesterday, then dates', () => {
    expect(relativeTime('2026-10-07T11:59:40Z', NOW)).toBe('Just now')
    expect(relativeTime('2026-10-07T11:55:00Z', NOW)).toBe('5 minutes ago')
    expect(relativeTime('2026-10-07T11:00:00Z', NOW)).toBe('1 hour ago')
    expect(relativeTime('2026-10-06T08:00:00Z', NOW)).toBe('Yesterday')
    expect(relativeTime('2026-09-01T08:00:00Z', NOW)).toMatch(/^1 Sep/)
  })
})

describe('daysLeft', () => {
  it('counts whole days to the purge and never goes below zero', () => {
    expect(daysLeft('2026-11-04T12:00:00Z', NOW)).toBe(28)
    expect(daysLeft('2026-10-01T12:00:00Z', NOW)).toBe(0)
    expect(daysLeft(null, NOW)).toBe(0)
  })
})

describe('pluralize and formatBytes', () => {
  it('uses Indian digit grouping and singular for one', () => {
    expect(pluralize(1, 'note')).toBe('1 note')
    expect(pluralize(1200000, 'note')).toBe('12,00,000 notes')
  })

  it('shows bytes, KB and MB', () => {
    expect(formatBytes(512)).toBe('512 B')
    expect(formatBytes(2048)).toBe('2 KB')
    expect(formatBytes(5 * 1024 * 1024)).toBe('5.0 MB')
    expect(formatBytes(412 * 1024 * 1024)).toBe('412 MB')
  })
})
