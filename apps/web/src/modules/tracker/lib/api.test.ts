import { describe, expect, it } from 'vitest'

import { ApiError } from '~/lib/api'

import { errorCode, errorMessage, isFeatureDisabled } from './api'

const err = (status: number, body?: unknown) => new ApiError(status, 'x', body)

describe('isFeatureDisabled', () => {
  it('is true only for a 403 carrying the feature_disabled code', () => {
    expect(isFeatureDisabled(err(403, { error: { code: 'feature_disabled' } }))).toBe(true)
    expect(isFeatureDisabled(err(403, { error: { code: 'other' } }))).toBe(false)
    expect(isFeatureDisabled(err(500, { error: { code: 'feature_disabled' } }))).toBe(false)
    expect(isFeatureDisabled(new Error('x'))).toBe(false)
  })
})

describe('errorCode and errorMessage', () => {
  it('reads the standard error shape', () => {
    const e = err(409, { error: { code: 'overlap', message: 'That time overlaps.' } })
    expect(errorCode(e)).toBe('overlap')
    expect(errorMessage(e)).toBe('That time overlaps.')
  })
  it('falls back for anything else', () => {
    expect(errorCode(new Error('x'))).toBeNull()
    expect(errorMessage(new Error('x'))).toMatch(/try again/i)
  })
})
