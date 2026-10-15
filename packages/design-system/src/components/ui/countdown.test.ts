import { describe, expect, it } from 'vitest'

import { formatCountdownTime } from './countdown'

describe('formatCountdownTime', () => {
  it('formats mm:ss when under 1 hour', () => {
    expect(formatCountdownTime(0)).toBe('00:00')
    expect(formatCountdownTime(-5)).toBe('00:00')
    expect(formatCountdownTime(65)).toBe('01:05')
    expect(formatCountdownTime(599)).toBe('09:59')
    expect(formatCountdownTime(3599)).toBe('59:59')
  })

  it('formats hh:mm:ss when 1 hour or more', () => {
    expect(formatCountdownTime(3600)).toBe('1:00:00')
    expect(formatCountdownTime(3665)).toBe('1:01:05')
    expect(formatCountdownTime(7200)).toBe('2:00:00')
  })
})
