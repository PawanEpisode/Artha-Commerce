import { describe, expect, it } from 'vitest'

import { ApiError } from '~/lib/api'

import { describeUploadError } from './avatarErrors'

const err = (status: number, code?: string, retryAfter?: number) => {
  const e = new ApiError(status, 'x', code ? { error: { code } } : undefined)
  e.retryAfter = retryAfter
  return e
}

describe('describeUploadError', () => {
  it('names the minutes when rate limited', () => {
    expect(describeUploadError(err(429, 'throttled', 700))).toEqual({
      reason: 'rate_limited',
      message: 'Too many changes. Try again in 12 minutes.',
    })
    expect(describeUploadError(err(429, undefined, 30)).message).toBe('Too many changes. Try again in 1 minute.')
    expect(describeUploadError(err(429)).message).toContain('a little while')
  })
  it.each([
    ['invalid_image', 'type'],
    ['image_too_small', 'small'],
    ['image_too_large', 'size'],
    ['payload_too_large', 'size'],
  ])('%s -> %s', (code, reason) => {
    expect(describeUploadError(err(400, code)).reason).toBe(reason)
  })
  it('separates network from server failures', () => {
    expect(describeUploadError(err(0)).reason).toBe('network')
    expect(describeUploadError(err(503, 'storage_unavailable')).reason).toBe('server')
    expect(describeUploadError(new Error('boom')).reason).toBe('server')
  })
})
