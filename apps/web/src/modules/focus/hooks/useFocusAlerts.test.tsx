import { act, renderHook } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const state = vi.hoisted(() => ({ track: vi.fn() }))
vi.mock('~/modules/observability', () => ({ track: state.track }))
vi.mock('../lib/chime', () => ({ playChime: vi.fn() }))
vi.mock('../lib/notify', () => ({ notify: { phaseEnded: vi.fn(), targetReached: vi.fn() } }))

import { playChime } from '../lib/chime'
import type { FocusSettings, FocusTimer } from '../lib/types'
import { useFocusAlerts } from './useFocusAlerts'

const settings = {
  sound_enabled: false,
  volume: 0,
  notifications_enabled: true,
} as FocusSettings
const timer = (clientId: string, over: Partial<FocusTimer> = {}) =>
  ({
    client_id: clientId,
    phase: 'focus',
    status: 'running',
    round_number: 1,
    rounds_before_long: 4,
    ...over,
  }) as FocusTimer

const shown: Array<{ title: string; options: { tag?: string } }> = []

function stubBrowser(visibility: 'hidden' | 'visible', permission: NotificationPermission = 'granted') {
  shown.length = 0
  class FakeNotification {
    static permission = permission
    constructor(title: string, options: { tag?: string }) {
      shown.push({ title, options })
    }
  }
  vi.stubGlobal('Notification', FakeNotification)
  vi.spyOn(document, 'visibilityState', 'get').mockReturnValue(visibility)
}

beforeEach(() => {
  state.track.mockClear()
  // Alerts are claimed in localStorage so that only one window plays each one.
  localStorage.clear()
  vi.mocked(playChime).mockClear()
})
afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

function run(first: FocusTimer | null, second: FocusTimer | null) {
  const quiet = { current: false }
  const hook = renderHook(({ t }) => useFocusAlerts(t, settings, quiet), { initialProps: { t: first } })
  hook.rerender({ t: second })
  return hook
}

describe('useFocusAlerts: one alert per timer end (FR-N5)', () => {
  it('the local alert carries the tag the push for that round carries, timer:<client_id>', () => {
    stubBrowser('hidden')
    run(timer('round-1'), timer('break-1', { phase: 'short_break' }))
    expect(shown).toHaveLength(1)
    expect(shown[0]?.options.tag).toBe('timer:round-1')
  })

  it('tells analytics which tag was shown locally', () => {
    stubBrowser('hidden')
    run(timer('round-1'), null)
    expect(state.track).toHaveBeenCalledWith('local_alert_shown', { tag: 'timer:round-1' })
  })

  it('a visible tab shows no system notification of its own: the push is the only one', () => {
    stubBrowser('visible')
    run(timer('round-1'), timer('break-1', { phase: 'short_break' }))
    expect(shown).toHaveLength(0)
    expect(state.track).not.toHaveBeenCalledWith('local_alert_shown', expect.anything())
  })

  it('reaching the target while overtime runs uses the running round’s tag', () => {
    stubBrowser('hidden')
    const hook = renderHook(() => useFocusAlerts(timer('round-9'), settings, { current: false }))
    act(() => hook.result.current.targetReached())
    expect(shown[0]?.options.tag).toBe('timer:round-9')
  })

  it('shows nothing when notifications are not allowed or the student ended the round themselves', () => {
    stubBrowser('hidden', 'denied')
    run(timer('round-1'), null)
    expect(shown).toHaveLength(0)

    stubBrowser('hidden')
    const quiet = { current: false }
    const hook = renderHook(({ t }) => useFocusAlerts(t, settings, quiet), {
      initialProps: { t: timer('a') as FocusTimer | null },
    })
    quiet.current = true // the student pressed Stop: they know, so nothing is announced
    hook.rerender({ t: null })
    expect(shown).toHaveLength(0)
  })

  it('counts a focus round that ended by itself, for the follow-up alerts ask, and not a break or a self-made end', () => {
    stubBrowser('visible')
    const quiet = { current: false }
    const hook = renderHook(({ t }) => useFocusAlerts(t, settings, quiet), {
      initialProps: { t: timer('round-1') as FocusTimer | null },
    })
    expect(hook.result.current.roundsFinished).toBe(0)
    hook.rerender({ t: timer('break-1', { phase: 'short_break' }) })
    expect(hook.result.current.roundsFinished).toBe(1)
    hook.rerender({ t: timer('round-2') }) // a break ended: not a finished round
    expect(hook.result.current.roundsFinished).toBe(1)
    quiet.current = true // the student stopped it themselves
    hook.rerender({ t: null })
    expect(hook.result.current.roundsFinished).toBe(1)
  })
})

describe('useFocusAlerts: more than one Artha window (X-01 W4.4)', () => {
  it('plays one chime and shows one notification for a phase end, however many windows ask', () => {
    stubBrowser('hidden')
    const loud = { ...settings, sound_enabled: true, volume: 0.5 } as FocusSettings
    const window1 = renderHook(({ t }) => useFocusAlerts(t, loud, { current: false }), {
      initialProps: { t: timer('round-1', { version: 3 }) as FocusTimer | null },
    })
    const window2 = renderHook(({ t }) => useFocusAlerts(t, loud, { current: false }), {
      initialProps: { t: timer('round-1', { version: 3 }) as FocusTimer | null },
    })
    window1.rerender({ t: timer('break-1', { phase: 'short_break' }) })
    window2.rerender({ t: timer('break-1', { phase: 'short_break' }) })
    expect(playChime).toHaveBeenCalledOnce()
    expect(shown).toHaveLength(1)
    // Both windows still announce it to their own screen readers.
    expect(window1.result.current.announcement).toContain('Focus round done')
    expect(window2.result.current.announcement).toContain('Focus round done')
  })

  it('shows no notification while another Artha window is visible', () => {
    stubBrowser('hidden')
    localStorage.setItem('artha:visible:other-window', String(Date.now()))
    run(timer('round-1'), timer('break-1', { phase: 'short_break' }))
    expect(shown).toHaveLength(0)
  })

  it('claims the target alert apart from the phase end of the same round', () => {
    stubBrowser('hidden')
    const loud = { ...settings, sound_enabled: true, volume: 0.5 } as FocusSettings
    const quiet = { current: false }
    const hook = renderHook(({ t }) => useFocusAlerts(t, loud, quiet), {
      initialProps: { t: timer('round-1', { version: 2 }) as FocusTimer | null },
    })
    act(() => hook.result.current.targetReached())
    hook.rerender({ t: null })
    expect(playChime).toHaveBeenCalledTimes(2)
  })
})
