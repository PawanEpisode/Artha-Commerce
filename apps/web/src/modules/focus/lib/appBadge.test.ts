import { describe, expect, it, vi } from 'vitest'

import { applyAppBadge, badgeWanted } from './appBadge'

describe('badgeWanted', () => {
  it('is on while a round, a break or the stopwatch runs, with the flag on', () => {
    expect(badgeWanted({ flagOn: true, live: 'pomodoro' })).toBe(true)
    expect(badgeWanted({ flagOn: true, live: 'stopwatch' })).toBe(true)
  })

  it('is off when idle, before the first answer, or with the floating_timer flag off', () => {
    expect(badgeWanted({ flagOn: true, live: 'none' })).toBe(false)
    expect(badgeWanted({ flagOn: false, live: 'pomodoro' })).toBe(false)
  })
})

describe('applyAppBadge', () => {
  it('sets a plain dot, with no number, and clears it', () => {
    const nav = {
      setAppBadge: vi.fn().mockResolvedValue(undefined),
      clearAppBadge: vi.fn().mockResolvedValue(undefined),
    }
    applyAppBadge(true, nav)
    expect(nav.setAppBadge).toHaveBeenCalledWith()
    applyAppBadge(false, nav)
    expect(nav.clearAppBadge).toHaveBeenCalledOnce()
  })

  it('does nothing where the Badging API does not exist', () => {
    expect(() => applyAppBadge(true, {})).not.toThrow()
    expect(() => applyAppBadge(false, null)).not.toThrow()
  })

  it('swallows a refusal, sync or async', async () => {
    const nav = {
      setAppBadge: vi.fn().mockRejectedValue(new DOMException('not installed', 'InvalidStateError')),
      clearAppBadge: vi.fn(() => {
        throw new Error('no')
      }),
    }
    expect(() => applyAppBadge(true, nav)).not.toThrow()
    expect(() => applyAppBadge(false, nav)).not.toThrow()
    await Promise.resolve()
  })
})
