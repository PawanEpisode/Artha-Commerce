import { describe, expect, it } from 'vitest'

import { keepAwakeLabel, wantsWakeLock } from './wakeLock'

const on = { keep_awake: true, keep_awake_in_breaks: false }
const running = { running: true, focus: true }

describe('wantsWakeLock (FR-K1, FR-K2)', () => {
  it('holds while a focus round or the stopwatch runs', () => {
    expect(wantsWakeLock(running, on)).toBe(true)
  })

  it('releases when the timer is not running (paused, away, idle prompt)', () => {
    expect(wantsWakeLock({ running: false, focus: true }, on)).toBe(false)
  })

  it('does nothing without a timer or settings', () => {
    expect(wantsWakeLock(null, on)).toBe(false)
    expect(wantsWakeLock(running, undefined)).toBe(false)
  })

  it('does not hold when the switch is off, even if breaks are on', () => {
    expect(wantsWakeLock(running, { keep_awake: false, keep_awake_in_breaks: true })).toBe(false)
  })

  it('holds a break only when the break switch is on', () => {
    const onBreak = { running: true, focus: false }
    expect(wantsWakeLock(onBreak, on)).toBe(false)
    expect(wantsWakeLock(onBreak, { ...on, keep_awake_in_breaks: true })).toBe(true)
  })
})

describe('keepAwakeLabel (FR-K4)', () => {
  it('names the two visible states', () => {
    expect(keepAwakeLabel('held')).toBe('Screen stays on')
    expect(keepAwakeLabel('sleep')).toBe('Screen may sleep')
  })

  it.each(['off', 'checking', 'unsupported'] as const)('shows nothing for %s', (status) => {
    expect(keepAwakeLabel(status)).toBeNull()
  })
})
