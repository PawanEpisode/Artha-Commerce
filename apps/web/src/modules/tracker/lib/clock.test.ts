import { afterEach, describe, expect, it, vi } from 'vitest'

import { clockOffsetMs, nowIso, nowMs, resetClock, setServerTime } from './clock'

afterEach(() => {
  resetClock()
  vi.useRealTimers()
})

describe('server clock', () => {
  it('corrects a device clock that runs fast', () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-10-05T10:00:00Z')) // device says 10:00
    setServerTime('2026-10-05T09:50:00Z') // server says 09:50
    expect(clockOffsetMs()).toBe(-600_000)
    expect(nowIso()).toBe('2026-10-05T09:50:00.000Z')
    vi.advanceTimersByTime(60_000)
    expect(nowMs()).toBe(Date.parse('2026-10-05T09:51:00Z'))
  })
  it('ignores a time it cannot read', () => {
    setServerTime('not a date')
    expect(clockOffsetMs()).toBe(0)
  })
})
