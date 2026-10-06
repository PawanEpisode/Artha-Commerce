import { act, renderHook } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const state = vi.hoisted(() => ({ track: vi.fn() }))
vi.mock('~/modules/observability', () => ({ track: state.track }))
vi.mock('../lib/chime', () => ({ playChime: vi.fn() }))
vi.mock('../lib/notify', () => ({ notify: { phaseEnded: vi.fn(), targetReached: vi.fn() } }))

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

beforeEach(() => state.track.mockClear())
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
})
