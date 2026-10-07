import { afterEach, beforeEach, describe, expect, it } from 'vitest'

import { resetClock, setServerTime } from '~/modules/tracker'

import { PRESENCE_WINDOW_SECONDS } from './popout'
import {
  popoutPresence,
  recordPopoutTap,
  resetPopoutPresence,
  setPopoutOpen,
  setPopoutVisible,
  setPresenceTarget,
} from './popout-presence'

const TARGET = Date.parse('2026-10-05T05:00:00Z')

beforeEach(() => {
  resetPopoutPresence()
  setServerTime(new Date(TARGET).toISOString(), Date.now())
})
afterEach(() => resetClock())

describe('popout presence state', () => {
  it('is closed until the window says it opened, and hidden windows do not count', () => {
    expect(popoutPresence(TARGET).popoutOpen).toBe(false)
    setPopoutOpen(true)
    expect(popoutPresence(TARGET).popoutOpen).toBe(true)
    setPopoutVisible(false)
    expect(popoutPresence(TARGET).popoutOpen).toBe(false)
    setPopoutOpen(false)
    setPopoutOpen(true)
    expect(popoutPresence(TARGET).popoutOpen).toBe(true)
  })

  it('follows a round across its target: present, then needs a tap, then present again', () => {
    setPopoutOpen(true)
    setPresenceTarget(TARGET)
    expect(popoutPresence(TARGET - 1000)).toMatchObject({ pastTarget: false, tappedSinceTarget: false })
    expect(popoutPresence(TARGET + 1000)).toMatchObject({ pastTarget: true, tappedSinceTarget: false })
    recordPopoutTap(TARGET + 30_000)
    expect(popoutPresence(TARGET + 60_000)).toMatchObject({ pastTarget: true, tappedSinceTarget: true })
  })

  it('ignores a tap after the presence window', () => {
    setPresenceTarget(TARGET)
    recordPopoutTap(TARGET + (PRESENCE_WINDOW_SECONDS + 1) * 1000)
    expect(popoutPresence(TARGET + 300_000).tappedSinceTarget).toBe(false)
  })

  it('starts a new window for a new target (a new round, a resume) and keeps it for the same one', () => {
    setPresenceTarget(TARGET)
    recordPopoutTap(TARGET + 1000)
    setPresenceTarget(TARGET)
    expect(popoutPresence(TARGET + 2000).tappedSinceTarget).toBe(true)
    setPresenceTarget(TARGET + 60_000)
    expect(popoutPresence(TARGET + 2000).tappedSinceTarget).toBe(false)
    setPresenceTarget(null)
    expect(popoutPresence(TARGET + 2000).pastTarget).toBe(false)
  })
})
