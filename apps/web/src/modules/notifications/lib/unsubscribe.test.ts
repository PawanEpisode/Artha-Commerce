import { describe, expect, it } from 'vitest'

import { ApiError } from '~/lib/api'

import { unsubscribeStatus } from './unsubscribe'

const base = {
  token: 'abc',
  previewLoading: false,
  previewError: null,
  confirming: false,
  confirmed: false,
  confirmError: null,
}

describe('unsubscribeStatus', () => {
  it('has no link to work with when the token is missing', () => {
    expect(unsubscribeStatus({ ...base, token: undefined })).toBe('invalid')
    expect(unsubscribeStatus({ ...base, token: '' })).toBe('invalid')
  })

  it('checks the link, then asks for one click', () => {
    expect(unsubscribeStatus({ ...base, previewLoading: true })).toBe('checking')
    expect(unsubscribeStatus(base)).toBe('ready')
  })

  it('works, then is done', () => {
    expect(unsubscribeStatus({ ...base, confirming: true })).toBe('working')
    expect(unsubscribeStatus({ ...base, confirmed: true })).toBe('done')
  })

  it('treats a 400 as a link that is not valid and anything else as a retryable error', () => {
    expect(unsubscribeStatus({ ...base, previewError: new ApiError(400, 'bad') })).toBe('invalid')
    expect(unsubscribeStatus({ ...base, previewError: new ApiError(429, 'slow down') })).toBe('error')
    expect(unsubscribeStatus({ ...base, previewError: new TypeError('network') })).toBe('error')
    expect(unsubscribeStatus({ ...base, confirmError: new ApiError(400, 'bad') })).toBe('invalid')
    expect(unsubscribeStatus({ ...base, confirmError: new ApiError(503, 'down') })).toBe('error')
  })
})
