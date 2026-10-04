import { describe, expect, it } from 'vitest'

import { secondsRemaining } from './cooldown'

describe('secondsRemaining', () => {
  it('rounds up and never goes negative', () => {
    expect(secondsRemaining(60_000, 0)).toBe(60)
    expect(secondsRemaining(60_000, 59_001)).toBe(1)
    expect(secondsRemaining(60_000, 60_000)).toBe(0)
    expect(secondsRemaining(60_000, 90_000)).toBe(0)
  })
})
