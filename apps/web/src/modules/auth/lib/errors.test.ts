import { describe, expect, it } from 'vitest'

import { friendlyAuthError, GENERIC_AUTH_ERROR, isReauthRequired } from './errors'

describe('friendlyAuthError', () => {
  it('maps known codes', () => {
    expect(friendlyAuthError({ code: 'invalid_credentials' })).toMatch(/do not match/)
    expect(friendlyAuthError({ code: 'otp_expired' })).toMatch(/expired/)
    expect(friendlyAuthError({ code: 'weak_password' })).toMatch(/stronger/)
  })
  it('handles rate limits by status', () => expect(friendlyAuthError({ status: 429 })).toMatch(/wait/))
  it('recognises expired token wording without a code', () => {
    expect(friendlyAuthError({ message: 'Email link is invalid or has expired' })).toMatch(/expired/)
  })
  it('never leaks raw server text', () => {
    expect(friendlyAuthError({ message: 'duplicate key value violates constraint users_pkey' })).toBe(
      GENERIC_AUTH_ERROR,
    )
    expect(friendlyAuthError(null)).toBe(GENERIC_AUTH_ERROR)
  })
  it('detects reauthentication', () => {
    expect(isReauthRequired({ code: 'reauthentication_needed' })).toBe(true)
    expect(isReauthRequired({ code: 'other' })).toBe(false)
    expect(isReauthRequired(undefined)).toBe(false)
  })
})
