import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

import { describe, expect, it } from 'vitest'

import { MAX_ACTIVE_DEVICES, TEST_COOLDOWN_MAX_SECONDS, TEST_COOLDOWN_SECONDS, TEST_PUSH_PER_MINUTE } from './limits'

const settings = readFileSync(fileURLToPath(new URL('../../../../../api/config/settings.py', import.meta.url)), 'utf8')

describe('limits mirrored from the API', () => {
  it('has the API test-push throttle (notifications_test)', () => {
    const rate = /"notifications_test":\s*"(\d+)\/min"/.exec(settings)
    expect(rate, 'notifications_test must be a per-minute rate in settings.py').not.toBeNull()
    expect(TEST_PUSH_PER_MINUTE).toBe(Number(rate?.[1]))
  })

  it('rests the test button for at least one throttle window', () => {
    expect(TEST_COOLDOWN_SECONDS).toBe(60)
    expect(TEST_COOLDOWN_MAX_SECONDS).toBeGreaterThanOrEqual(TEST_COOLDOWN_SECONDS)
  })

  it('shows the PRD device limit (Q9)', () => {
    expect(MAX_ACTIVE_DEVICES).toBe(10)
  })
})
