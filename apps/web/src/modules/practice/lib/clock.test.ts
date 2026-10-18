import { describe, expect, it } from 'vitest'

import { clockOffsetMs, type ClockSource, countdownAnnouncement, practiceClock } from './clock'

const T0 = Date.parse('2026-10-18T10:00:00Z')
const iso = (offsetSeconds: number) => new Date(T0 + offsetSeconds * 1000).toISOString()

/** A session started at T0, seen by a device whose clock agrees with the server. */
const base = (over: Partial<ClockSource> = {}): ClockSource => ({
  status: 'in_progress',
  time_limit_seconds: 600,
  started_at: iso(0),
  deadline_at: iso(600),
  paused_at: null,
  paused_total_seconds: 0,
  server_now: iso(0),
  receivedAtMs: T0,
  ...over,
})

describe('practiceClock', () => {
  it('waits for a session that has not started or has ended', () => {
    expect(practiceClock(base({ status: 'created', started_at: null, deadline_at: null }), T0)).toEqual({
      kind: 'waiting',
    })
    expect(practiceClock(base({ status: 'submitted' }), T0)).toEqual({ kind: 'waiting' })
    expect(practiceClock(base({ started_at: 'not a date' }), T0)).toEqual({ kind: 'waiting' })
  })

  it('counts down to the deadline', () => {
    expect(practiceClock(base(), T0)).toEqual({ kind: 'countdown', seconds: 600, paused: false, expired: false })
    expect(practiceClock(base(), T0 + 125_000)).toMatchObject({ seconds: 475 })
  })

  it('rounds a partial second up so the clock never shows 00:00 before time is up', () => {
    expect(practiceClock(base(), T0 + 599_100)).toMatchObject({ seconds: 1, expired: false })
  })

  it('expires at the deadline and stays at zero after it', () => {
    expect(practiceClock(base(), T0 + 600_000)).toMatchObject({ seconds: 0, expired: true })
    expect(practiceClock(base(), T0 + 9_000_000)).toMatchObject({ seconds: 0, expired: true })
  })

  it('stands still while paused, frozen at the moment of the pause', () => {
    const paused = base({ status: 'paused', paused_at: iso(100) })
    expect(practiceClock(paused, T0 + 100_000)).toMatchObject({ seconds: 500, paused: true, expired: false })
    expect(practiceClock(paused, T0 + 5_000_000)).toMatchObject({ seconds: 500, paused: true, expired: false })
  })

  it('does not lose the time spent paused earlier once the deadline has been pushed back', () => {
    // Paused 60s, resumed: the server moved the deadline from 600 to 660.
    const resumed = base({ deadline_at: iso(660), paused_total_seconds: 60 })
    expect(practiceClock(resumed, T0 + 160_000)).toMatchObject({ seconds: 500 })
  })

  it('falls back to start + limit + paused time when the deadline is missing', () => {
    const noDeadline = base({ deadline_at: null, paused_total_seconds: 30 })
    expect(practiceClock(noDeadline, T0)).toMatchObject({ seconds: 630 })
  })

  it('counts up for an untimed session', () => {
    const untimed = base({ time_limit_seconds: null, deadline_at: null })
    expect(practiceClock(untimed, T0 + 90_000)).toEqual({ kind: 'elapsed', seconds: 90, paused: false, expired: false })
  })

  it('leaves paused time out of the time spent', () => {
    const untimed = base({ time_limit_seconds: null, deadline_at: null, paused_total_seconds: 40 })
    expect(practiceClock(untimed, T0 + 100_000)).toMatchObject({ seconds: 60 })
    const paused = { ...untimed, status: 'paused', paused_at: iso(70) }
    expect(practiceClock(paused, T0 + 999_000)).toMatchObject({ seconds: 30, paused: true })
  })
})

describe('device clock that disagrees with the server', () => {
  it('measures the offset when the data arrived', () => {
    expect(clockOffsetMs({ server_now: iso(0), receivedAtMs: T0 + 5000 })).toBe(5000)
    expect(clockOffsetMs({ server_now: 'garbage', receivedAtMs: T0 })).toBe(0)
  })

  it('does not let a fast device clock shorten the exam', () => {
    // The device runs 10 minutes ahead; the student has really had 100 seconds.
    const fast = base({ receivedAtMs: T0 + 600_000 })
    expect(practiceClock(fast, T0 + 600_000 + 100_000)).toMatchObject({ seconds: 500 })
  })

  it('does not let a slow device clock stretch it', () => {
    const slow = base({ receivedAtMs: T0 - 600_000 })
    expect(practiceClock(slow, T0 - 600_000 + 100_000)).toMatchObject({ seconds: 500 })
  })
})

describe('countdownAnnouncement', () => {
  it('speaks only when a warning mark is crossed', () => {
    expect(countdownAnnouncement(601, 600)).toBe('10 minutes left.')
    expect(countdownAnnouncement(301, 300)).toBe('5 minutes left.')
    expect(countdownAnnouncement(61, 60)).toBe('1 minute left.')
    expect(countdownAnnouncement(1, 0)).toBe('Time is up.')
  })

  it('is silent between marks, on first sight and when time moves backwards', () => {
    expect(countdownAnnouncement(500, 499)).toBeNull()
    expect(countdownAnnouncement(null, 59)).toBeNull()
    expect(countdownAnnouncement(300, 301)).toBeNull()
  })

  it('names the lowest mark when a long gap skips several', () => {
    expect(countdownAnnouncement(700, 40)).toBe('1 minute left.')
  })
})
