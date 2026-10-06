import { describe, expect, it, vi } from 'vitest'

import type { Environment } from './platform'
import type { PushBrowser, PushSubscriptionLike } from './push'
import { buildRegistration, syncCurrentDevice } from './register'

const environment: Environment = {
  platform: 'android',
  browser: 'chrome',
  displayMode: 'browser',
  inAppBrowser: null,
  support: 'supported',
  label: 'Chrome on Android',
}
const subscription: PushSubscriptionLike = {
  endpoint: 'https://push.example.test/abc',
  toJSON: () => ({ endpoint: 'https://push.example.test/abc', keys: { p256dh: 'P', auth: 'A' } }),
  unsubscribe: vi.fn(),
}
const browser = (permission: 'granted' | 'default' | 'denied', current: PushSubscriptionLike | null): PushBrowser => ({
  permission: () => permission,
  requestPermission: vi.fn(),
  registration: vi
    .fn()
    .mockResolvedValue({ pushManager: { getSubscription: async () => current, subscribe: vi.fn() } }),
})

describe('buildRegistration', () => {
  it('matches the POST devices/ contract', () => {
    expect(buildRegistration(subscription, environment)).toEqual({
      endpoint: 'https://push.example.test/abc',
      keys: { p256dh: 'P', auth: 'A' },
      platform: 'android',
      browser: 'chrome',
      display_mode: 'browser',
      sw_version: 'dev',
      label: 'Chrome on Android',
    })
  })
})

describe('syncCurrentDevice', () => {
  it('registers the subscription the browser holds and returns the device id', async () => {
    const register = vi.fn().mockResolvedValue('dev-1')
    await expect(syncCurrentDevice({ browser: browser('granted', subscription), environment, register })).resolves.toBe(
      'dev-1',
    )
    expect(register).toHaveBeenCalledWith(expect.objectContaining({ endpoint: 'https://push.example.test/abc' }))
  })

  it('does nothing without permission or without a subscription', async () => {
    const register = vi.fn()
    await expect(
      syncCurrentDevice({ browser: browser('default', subscription), environment, register }),
    ).resolves.toBeNull()
    await expect(
      syncCurrentDevice({ browser: browser('denied', subscription), environment, register }),
    ).resolves.toBeNull()
    await expect(syncCurrentDevice({ browser: browser('granted', null), environment, register })).resolves.toBeNull()
    expect(register).not.toHaveBeenCalled()
  })
})
