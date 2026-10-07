import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const state = vi.hoisted(() => ({ getTimer: vi.fn() }))
vi.mock('../lib/api', async () => ({
  ...(await vi.importActual<Record<string, unknown>>('../lib/api')),
  getTimer: state.getTimer,
}))

import { markActive, resetClock } from '~/modules/tracker'

import { recordPopoutTap, resetPopoutPresence, setPopoutOpen, setPresenceTarget } from '../lib/popout-presence'
import { fetchTimerState } from './useFocusTimer'

const FIVE_MINUTES = 5 * 60_000

beforeEach(() => {
  vi.useFakeTimers({ toFake: ['Date'] })
  // Long enough after the module loaded that "recently active" is false until a test taps.
  vi.setSystemTime(Date.now() + 10 * 60_000)
  resetClock()
  resetPopoutPresence()
  state.getTimer.mockReset()
  state.getTimer.mockImplementation(async () => ({ server_time: new Date().toISOString(), timer: null }))
})
afterEach(() => {
  vi.useRealTimers()
  vi.restoreAllMocks()
})

const hidden = () => vi.spyOn(document, 'visibilityState', 'get').mockReturnValue('hidden')
const visible = () => vi.spyOn(document, 'visibilityState', 'get').mockReturnValue('visible')
const alive = async () => {
  await fetchTimerState()
  return state.getTimer.mock.calls.at(-1)?.[0]
}

describe('fetchTimerState: who counts as present', () => {
  it("is today's rule for a visible tab with a recent tap", async () => {
    visible()
    markActive()
    expect(await alive()).toBe(true)
  })

  it('is not present for a visible tab that nobody has touched for five minutes', async () => {
    visible()
    vi.setSystemTime(Date.now() + FIVE_MINUTES + 1000)
    expect(await alive()).toBe(false)
  })

  it('is not present for a hidden tab with no pop-out', async () => {
    hidden()
    expect(await alive()).toBe(false)
  })

  it('counts an open pop-out until the target even with the tab hidden and nobody tapping', async () => {
    hidden()
    setPopoutOpen(true)
    setPresenceTarget(Date.now() + 600_000)
    expect(await alive()).toBe(true)
  })

  it('stops counting it after the target, until a tap in the window', async () => {
    hidden()
    setPopoutOpen(true)
    setPresenceTarget(Date.now() - 1000)
    expect(await alive()).toBe(false)
    recordPopoutTap(Date.now())
    expect(await alive()).toBe(true)
  })

  it('does not count a pop-out that is closed', async () => {
    hidden()
    setPresenceTarget(Date.now() + 600_000)
    expect(await alive()).toBe(false)
  })
})
