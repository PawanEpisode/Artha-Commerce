import { describe, expect, it } from 'vitest'

import { avatarColourIndex, initialsOf } from './initials'

describe('initialsOf', () => {
  it.each([
    ['Aarav Mehta', 'AM'],
    ['  aarav   kumar   mehta ', 'AM'],
    ['Aarav', 'A'],
    ['priya', 'P'],
    ['आरव मेहता', 'आमे'],
    ['தமிழ் செல்வன்', 'தசெ'],
    ['Zoë Ångström', 'ZÅ'],
  ])('%s -> %s', (name, expected) => {
    expect(initialsOf(name)).toBe(expected)
  })

  it('keeps a whole combining cluster, not half a letter', () => {
    expect(initialsOf('क्षमा')).toBe('क्ष')
  })

  it('falls back to the email, then to a question mark', () => {
    expect(initialsOf('', 'zed@example.com')).toBe('Z')
    expect(initialsOf('   ', 'zed@example.com')).toBe('Z')
    expect(initialsOf(null, null)).toBe('?')
    expect(initialsOf('', '')).toBe('?')
  })
})

describe('avatarColourIndex', () => {
  it('is stable and within 1 to 8', () => {
    const id = '3f2b8c7e-6d2e-4f0e-9a45-0f9e5b3e1c11'
    expect(avatarColourIndex(id)).toBe(avatarColourIndex(id))
    for (let i = 0; i < 500; i++) {
      const n = avatarColourIndex(`user-${i}`)
      expect(n).toBeGreaterThanOrEqual(1)
      expect(n).toBeLessThanOrEqual(8)
    }
  })

  it('spreads users over all eight colours', () => {
    const seen = new Set(Array.from({ length: 400 }, (_, i) => avatarColourIndex(`id-${i}`)))
    expect(seen.size).toBe(8)
  })
})
