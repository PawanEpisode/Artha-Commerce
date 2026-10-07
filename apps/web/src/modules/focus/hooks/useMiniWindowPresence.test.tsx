import { renderHook } from '@testing-library/react'
import { fireEvent } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { popoutPresence, resetPopoutPresence } from '../lib/popout-presence'
import type { FocusTimer } from '../lib/types'
import { useMiniWindowPresence } from './useMiniWindowPresence'

const NOW = Date.parse('2026-10-05T04:40:00Z')
// A round that reached its target 10 seconds ago.
const running = {
  phase: 'focus',
  status: 'running',
  planned_seconds: 1500,
  started_at: new Date(NOW - 1510_000).toISOString(),
  paused_total_seconds: 0,
} as FocusTimer

afterEach(() => {
  resetPopoutPresence()
  vi.restoreAllMocks()
  vi.useRealTimers()
})

describe('useMiniWindowPresence', () => {
  it('counts the window as open while it is mounted and visible, and as closed after', () => {
    const hook = renderHook(() => useMiniWindowPresence(null))
    expect(popoutPresence().popoutOpen).toBe(true)
    hook.unmount()
    expect(popoutPresence().popoutOpen).toBe(false)
  })

  it('judges it by its own visibility: hidden behind other windows does not count', () => {
    const state = vi.spyOn(document, 'visibilityState', 'get').mockReturnValue('hidden')
    renderHook(() => useMiniWindowPresence(null))
    expect(popoutPresence().popoutOpen).toBe(false)
    state.mockReturnValue('visible')
    fireEvent(document, new Event('visibilitychange'))
    expect(popoutPresence().popoutOpen).toBe(true)
  })

  it('needs one tap in the window after the target for the extra time to count', () => {
    vi.useFakeTimers({ toFake: ['Date'] })
    vi.setSystemTime(NOW)
    renderHook(() => useMiniWindowPresence(running))
    expect(popoutPresence(NOW).pastTarget).toBe(true)
    expect(popoutPresence(NOW).tappedSinceTarget).toBe(false)
    fireEvent.pointerDown(window)
    expect(popoutPresence(NOW).tappedSinceTarget).toBe(true)
  })
})
