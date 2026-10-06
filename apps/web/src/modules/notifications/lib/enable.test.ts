import { describe, expect, it, vi } from 'vitest'

import { ApiError } from '~/lib/api'

import { enableAlerts, type EnableDeps } from './enable'
import type { Environment } from './platform'
import type { PushBrowser, PushSubscriptionLike } from './push'

const KEY_BYTES = new Uint8Array(65).map((_, i) => (i === 0 ? 4 : 5))
const VAPID = btoa(String.fromCharCode(...KEY_BYTES))
  .replace(/\+/g, '-')
  .replace(/\//g, '_')
  .replace(/=+$/, '')

const environment: Environment = {
  platform: 'windows',
  browser: 'chrome',
  displayMode: 'browser',
  inAppBrowser: null,
  support: 'supported',
  label: 'Chrome on Windows',
}

function setup(
  options: {
    permission?: 'default' | 'granted' | 'denied' | 'unsupported'
    answer?: NotificationPermission
    register?: () => Promise<string>
  } = {},
) {
  const subscription: PushSubscriptionLike = {
    endpoint: 'https://push.example.test/e',
    toJSON: () => ({ endpoint: 'https://push.example.test/e', keys: { p256dh: 'P', auth: 'A' } }),
    unsubscribe: vi.fn().mockResolvedValue(true),
  }
  const browser: PushBrowser = {
    permission: () => options.permission ?? 'default',
    requestPermission: vi.fn().mockResolvedValue(options.answer ?? 'granted'),
    registration: vi.fn().mockResolvedValue({
      pushManager: { getSubscription: async () => null, subscribe: vi.fn().mockResolvedValue(subscription) },
    }),
  }
  const analytics = { permissionPrompted: vi.fn(), permissionResult: vi.fn() }
  const api = {
    registerDevice: vi.fn(options.register ?? (async () => 'dev-1')),
    postPermissionState: vi.fn().mockResolvedValue({}),
  }
  const deps: EnableDeps = { browser, environment, vapidPublicKey: VAPID, source: 'settings', analytics, api }
  return { deps, browser, analytics, api, subscription }
}

describe('enableAlerts', () => {
  it('prompts, subscribes, records the decision and registers the device', async () => {
    const { deps, analytics, api, browser } = setup()
    await expect(enableAlerts(deps)).resolves.toEqual({ status: 'enabled', deviceId: 'dev-1' })
    expect(browser.requestPermission).toHaveBeenCalledTimes(1)
    expect(analytics.permissionPrompted).toHaveBeenCalledWith('settings')
    expect(analytics.permissionResult).toHaveBeenCalledWith('granted', 'settings')
    expect(api.postPermissionState).toHaveBeenCalledWith('granted', 'settings')
    expect(api.registerDevice).toHaveBeenCalledWith(
      expect.objectContaining({
        endpoint: 'https://push.example.test/e',
        platform: 'windows',
        browser: 'chrome',
        display_mode: 'browser',
      }),
    )
  })

  it('does not report a prompt when permission was already granted, but still syncs the decision', async () => {
    const { deps, analytics, api } = setup({ permission: 'granted' })
    await expect(enableAlerts(deps)).resolves.toMatchObject({ status: 'enabled' })
    expect(analytics.permissionPrompted).not.toHaveBeenCalled()
    expect(analytics.permissionResult).not.toHaveBeenCalled()
    expect(api.postPermissionState).toHaveBeenCalledWith('granted', 'settings')
  })

  it('reports "Block" as denied, and never registers', async () => {
    const { deps, analytics, api } = setup({ answer: 'denied' })
    await expect(enableAlerts(deps)).resolves.toEqual({ status: 'denied' })
    expect(analytics.permissionResult).toHaveBeenCalledWith('denied', 'settings')
    expect(api.postPermissionState).toHaveBeenCalledWith('denied', 'settings')
    expect(api.registerDevice).not.toHaveBeenCalled()
  })

  it('reports a closed prompt as dismissed', async () => {
    const { deps, analytics, api } = setup({ answer: 'default' })
    await expect(enableAlerts(deps)).resolves.toEqual({ status: 'dismissed' })
    expect(analytics.permissionResult).toHaveBeenCalledWith('dismissed', 'settings')
    expect(api.postPermissionState).toHaveBeenCalledWith('dismissed', 'settings')
  })

  it('does nothing for a blocked site: no prompt, no event, no write', async () => {
    const { deps, analytics, api, browser } = setup({ permission: 'denied' })
    await expect(enableAlerts(deps)).resolves.toEqual({ status: 'blocked' })
    expect(browser.requestPermission).not.toHaveBeenCalled()
    expect(analytics.permissionPrompted).not.toHaveBeenCalled()
    expect(api.postPermissionState).not.toHaveBeenCalled()
  })

  it('reports an unsupported browser without writing', async () => {
    const { deps, api } = setup({ permission: 'unsupported' })
    await expect(enableAlerts(deps)).resolves.toEqual({ status: 'unsupported' })
    expect(api.postPermissionState).not.toHaveBeenCalled()
  })

  it('keeps a working subscription when recording the decision fails', async () => {
    const { deps, api } = setup()
    api.postPermissionState.mockRejectedValue(new Error('offline'))
    await expect(enableAlerts(deps)).resolves.toMatchObject({ status: 'enabled' })
  })

  it('drops the browser subscription when the API says there are too many devices', async () => {
    const { deps, subscription } = setup({
      register: async () => {
        throw new ApiError(409, 'x', { error: { code: 'device_limit' } })
      },
    })
    await expect(enableAlerts(deps)).resolves.toEqual({ status: 'device_limit' })
    expect(subscription.unsubscribe).toHaveBeenCalled()
  })

  it('keeps the subscription and reports a plain failure for any other registration error', async () => {
    const { deps, subscription } = setup({
      register: async () => {
        throw new ApiError(500, 'x')
      },
    })
    await expect(enableAlerts(deps)).resolves.toEqual({ status: 'error', reason: 'register_failed' })
    expect(subscription.unsubscribe).not.toHaveBeenCalled()
  })

  it('counts a subscribe failure after the prompt as granted, and reports it', async () => {
    const { deps, analytics } = setup()
    deps.vapidPublicKey = 'not a key'
    await expect(enableAlerts(deps)).resolves.toEqual({ status: 'error', reason: 'bad_key' })
    expect(analytics.permissionResult).toHaveBeenCalledWith('granted', 'settings')
  })
})
