import { describe, expect, it } from 'vitest'

import { ApiError } from '~/lib/api'

import { canUnlock, isUnlocking, unlockErrorText, unlockStatusText } from './unlock-copy'

const doc = (over = {}) => ({
  status: 'needs_password' as const,
  unlock_status: 'none' as const,
  unlock_reason: null,
  is_encrypted: true,
  text_status: 'locked' as const,
  ...over,
})
const err = (status: number, code: string) => new ApiError(status, 'x', { error: { code, message: 'm' } })

describe('unlock for search copy', () => {
  it('offers unlocking only for a locked PDF with no try on its way', () => {
    expect(canUnlock(doc())).toBe(true)
    expect(canUnlock(doc({ unlock_status: 'running' }))).toBe(false)
    expect(canUnlock(doc({ status: 'ready' }))).toBe(false)
    expect(canUnlock(doc({ unlock_status: 'failed', unlock_reason: 'wrong_password' }))).toBe(true)
  })

  it('knows when a try is on its way', () => {
    expect(isUnlocking({ unlock_status: 'waiting' })).toBe(true)
    expect(isUnlocking({ unlock_status: 'done' })).toBe(false)
  })

  it('words every stage and every failure, and promises the password is not kept', () => {
    expect(unlockStatusText(doc())).toMatch(/locked/)
    expect(unlockStatusText(doc({ unlock_status: 'running' }))).toMatch(/Reading/)
    expect(unlockStatusText(doc({ status: 'ready', unlock_status: 'done' }))).toMatch(/not kept/)
    const failed = (unlock_reason: string) => unlockStatusText(doc({ unlock_status: 'failed', unlock_reason }))
    expect(failed('wrong_password')).toMatch(/did not open/)
    expect(failed('restricted')).toMatch(/does not allow/)
    expect(failed('expired')).toMatch(/discarded/)
    expect(failed('unreadable')).toMatch(/could not read/)
    expect(unlockStatusText(doc({ status: 'ready' }))).toBeNull()
  })

  it('words a refused request by its code', () => {
    expect(unlockErrorText(err(429, 'too_many_attempts'))).toMatch(/hour/)
    expect(unlockErrorText(err(503, 'unlock_unavailable'))).toMatch(/not available/)
    expect(unlockErrorText(err(409, 'unlock_in_progress'))).toMatch(/already/)
    expect(unlockErrorText(err(409, 'not_locked'))).toMatch(/does not need/)
    expect(unlockErrorText(err(500, 'x'))).toMatch(/Try again/)
  })
})
