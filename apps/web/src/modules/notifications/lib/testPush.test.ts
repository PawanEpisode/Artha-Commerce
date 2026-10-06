import { describe, expect, it } from 'vitest'

import { ApiError } from '~/lib/api'

import { TEST_COOLDOWN_MAX_SECONDS, TEST_COOLDOWN_SECONDS } from './limits'
import { pickTestDevice, statusFromError, testStatusMessage } from './testPush'

const err = (status: number, retryAfter?: number) => {
  const e = new ApiError(status, 'x')
  if (retryAfter !== undefined) e.retryAfter = retryAfter
  return e
}

describe('statusFromError', () => {
  it('rests for as long as the API asked on a 429', () => {
    expect(statusFromError(err(429, 17))).toEqual({ kind: 'rate_limited', seconds: 17 })
    expect(statusFromError(err(429, 4.2))).toEqual({ kind: 'rate_limited', seconds: 5 })
  })

  it('rests for a minute when the API did not say, and never longer than the cap', () => {
    expect(statusFromError(err(429))).toEqual({ kind: 'rate_limited', seconds: TEST_COOLDOWN_SECONDS })
    expect(statusFromError(err(429, 99999))).toEqual({ kind: 'rate_limited', seconds: TEST_COOLDOWN_MAX_SECONDS })
  })

  it('tells a missing device from other failures', () => {
    expect(statusFromError(err(404))).toEqual({ kind: 'device_gone' })
    expect(statusFromError(err(500))).toEqual({ kind: 'failed' })
    expect(statusFromError(new Error('offline'))).toEqual({ kind: 'failed' })
  })
})

describe('testStatusMessage', () => {
  it('has calm wording for every state, and says nothing when idle', () => {
    expect(testStatusMessage({ kind: 'idle' })).toBeNull()
    expect(testStatusMessage({ kind: 'sending' })).toMatch(/Sending/)
    expect(testStatusMessage({ kind: 'sent' })).toMatch(/Test sent/)
    expect(testStatusMessage({ kind: 'rate_limited', seconds: 30 })).toBe(
      'That was a lot of tests in a row. You can send another in 30 seconds.',
    )
    expect(testStatusMessage({ kind: 'rate_limited', seconds: 1 })).toMatch(/in 1 second\./)
    expect(testStatusMessage({ kind: 'device_gone' })).toMatch(/no longer registered/)
    expect(testStatusMessage({ kind: 'failed' })).toMatch(/could not send/)
  })
})

describe('pickTestDevice', () => {
  const devices = [
    { id: 'a', last_seen_at: '2026-10-01T10:00:00Z' },
    { id: 'b', last_seen_at: '2026-10-05T10:00:00Z' },
    { id: 'c', last_seen_at: null },
  ]
  it('prefers this browser, then the most recently seen device', () => {
    expect(pickTestDevice(devices, 'a')?.id).toBe('a')
    expect(pickTestDevice(devices, 'zzz')?.id).toBe('b')
    expect(pickTestDevice(devices, null)?.id).toBe('b')
  })
  it('is null with no devices', () => {
    expect(pickTestDevice([], 'a')).toBeNull()
  })
})
