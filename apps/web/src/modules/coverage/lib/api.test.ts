import { describe, expect, it } from 'vitest'

import { ApiError } from '~/lib/api'

import { isFeatureDisabled, isNoEnrollment } from './api'

const err = (status: number, body?: unknown) => new ApiError(status, 'x', body)

describe('isFeatureDisabled', () => {
  it('is true only for a 403 carrying the feature_disabled code', () => {
    expect(isFeatureDisabled(err(403, { error: { code: 'feature_disabled' } }))).toBe(true)
  })

  it('is false for other 403s, other statuses and non-API errors', () => {
    expect(isFeatureDisabled(err(403, { error: { code: 'permission_denied' } }))).toBe(false)
    expect(isFeatureDisabled(err(403))).toBe(false)
    expect(isFeatureDisabled(err(401, { error: { code: 'feature_disabled' } }))).toBe(false)
    expect(isFeatureDisabled(new Error('boom'))).toBe(false)
    expect(isFeatureDisabled(undefined)).toBe(false)
  })
})

describe('isNoEnrollment', () => {
  it('is a 404', () => {
    expect(isNoEnrollment(err(404))).toBe(true)
    expect(isNoEnrollment(err(403))).toBe(false)
  })
})
