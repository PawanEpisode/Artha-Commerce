import { describe, expect, it } from 'vitest'

import { friendlyDateTime } from './format'

describe('friendlyDateTime', () => {
  it('writes a datetime-local value in words, in the same wall-clock time', () => {
    expect(friendlyDateTime('2026-10-05T23:05')).toBe('Mon, 5 Oct 2026, 11:05 pm')
  })
  it('is empty for an empty or invalid value', () => {
    expect(friendlyDateTime('')).toBe('')
    expect(friendlyDateTime('nope')).toBe('')
  })
})
