import { describe, expect, it } from 'vitest'

import { ApiError } from '~/lib/api'

import { MAX_API_CALLS, retryDelay, shouldRetry } from './retry'

const err = (status: number) => new ApiError(status, 'x')

describe('shouldRetry', () => {
  it('never makes more than five calls in total', () => {
    const calls = (error: unknown) => {
      let n = 1
      while (shouldRetry(n - 1, error)) n++
      return n
    }
    expect(calls(err(503))).toBe(MAX_API_CALLS)
    expect(calls(new TypeError('Failed to fetch'))).toBe(MAX_API_CALLS)
    expect(MAX_API_CALLS).toBe(5)
  })

  it('does not repeat an answer that cannot change', () => {
    for (const status of [400, 401, 403, 404, 409, 422]) expect(shouldRetry(0, err(status))).toBe(false)
  })

  it('retries throttling, timeouts, server errors and dropped connections', () => {
    for (const status of [408, 429, 500, 502, 503, 504, 0]) expect(shouldRetry(0, err(status))).toBe(true)
    expect(shouldRetry(0, new TypeError('Failed to fetch'))).toBe(true)
  })

  it('leaves a cancelled call alone', () => {
    expect(shouldRetry(0, new DOMException('aborted', 'AbortError'))).toBe(false)
  })
})

describe('retryDelay', () => {
  it('backs off exponentially up to 30 seconds', () => {
    expect([0, 1, 2, 3, 9].map((n) => retryDelay(n, err(503)))).toEqual([1000, 2000, 4000, 8000, 30_000])
  })

  it('waits as long as the server asked when it throttles', () => {
    const throttled = err(429)
    throttled.retryAfter = 7
    expect(retryDelay(0, throttled)).toBe(7000)
    throttled.retryAfter = 600
    expect(retryDelay(0, throttled)).toBe(30_000)
  })
})
