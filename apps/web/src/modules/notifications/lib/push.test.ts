import { describe, expect, it, vi } from 'vitest'

import {
  enablePush,
  IncompleteSubscription,
  type PushBrowser,
  type PushRegistrationLike,
  type PushSubscriptionLike,
  subscribeToPush,
  toDeviceKeys,
  unsubscribeFromPush,
} from './push'

const KEY_BYTES = new Uint8Array(65).map((_, i) => (i === 0 ? 4 : (i * 3) % 256))
const VAPID = btoa(String.fromCharCode(...KEY_BYTES))
  .replace(/\+/g, '-')
  .replace(/\//g, '_')
  .replace(/=+$/, '')

function subscription(
  patch: Partial<PushSubscriptionLike> = {},
  keyBytes: Uint8Array = KEY_BYTES,
): PushSubscriptionLike {
  return {
    endpoint: 'https://push.example.test/abc',
    options: { applicationServerKey: keyBytes.buffer.slice(0) as ArrayBuffer },
    toJSON: () => ({ endpoint: 'https://push.example.test/abc', keys: { p256dh: 'P256', auth: 'AUTH' } }),
    unsubscribe: vi.fn().mockResolvedValue(true),
    ...patch,
  }
}

/** A faked PushManager: holds at most one subscription, like the real one. */
function fakeRegistration(initial: PushSubscriptionLike | null = null) {
  let current = initial
  const subscribe = vi.fn(async ({ applicationServerKey }: { applicationServerKey: BufferSource }) => {
    current = subscription({}, new Uint8Array(applicationServerKey as ArrayBuffer))
    return current
  })
  const registration: PushRegistrationLike = {
    pushManager: { getSubscription: vi.fn(async () => current), subscribe },
  }
  return {
    registration,
    subscribe,
    get current() {
      return current
    },
  }
}

function fakeBrowser(options: {
  permission?: ReturnType<PushBrowser['permission']>
  answer?: NotificationPermission
  registration?: PushRegistrationLike
  registrationError?: Error
}): PushBrowser & { requestPermission: ReturnType<typeof vi.fn> } {
  return {
    permission: () => options.permission ?? 'default',
    requestPermission: vi.fn().mockResolvedValue(options.answer ?? 'granted'),
    registration: options.registrationError
      ? vi.fn().mockRejectedValue(options.registrationError)
      : vi.fn().mockResolvedValue(options.registration ?? fakeRegistration().registration),
  }
}

describe('toDeviceKeys', () => {
  it('reads the endpoint and both keys', () => {
    expect(toDeviceKeys(subscription())).toEqual({
      endpoint: 'https://push.example.test/abc',
      keys: { p256dh: 'P256', auth: 'AUTH' },
    })
  })

  it('throws when the browser leaves a key out', () => {
    const incomplete = subscription({ toJSON: () => ({ endpoint: 'https://x.test', keys: { p256dh: 'P' } }) })
    expect(() => toDeviceKeys(incomplete)).toThrow(IncompleteSubscription)
  })
})

describe('subscribeToPush', () => {
  it('subscribes with the decoded key and userVisibleOnly', async () => {
    const fake = fakeRegistration()
    await subscribeToPush(fake.registration, VAPID)
    expect(fake.subscribe).toHaveBeenCalledTimes(1)
    const options = fake.subscribe.mock.calls[0]?.[0] as { userVisibleOnly: boolean; applicationServerKey: Uint8Array }
    expect(options.userVisibleOnly).toBe(true)
    expect([...options.applicationServerKey]).toEqual([...KEY_BYTES])
  })

  it('reuses an existing subscription made with the same key', async () => {
    const existing = subscription()
    const fake = fakeRegistration(existing)
    await expect(subscribeToPush(fake.registration, VAPID)).resolves.toBe(existing)
    expect(fake.subscribe).not.toHaveBeenCalled()
  })

  it('replaces a subscription made with an older key', async () => {
    const other = new Uint8Array(65).map((_, i) => (i === 0 ? 4 : 9))
    const stale = subscription({}, other)
    const fake = fakeRegistration(stale)
    await subscribeToPush(fake.registration, VAPID)
    expect(stale.unsubscribe).toHaveBeenCalled()
    expect(fake.subscribe).toHaveBeenCalledTimes(1)
  })
})

describe('enablePush', () => {
  it('prompts when undecided, then subscribes', async () => {
    const fake = fakeRegistration()
    const browser = fakeBrowser({ permission: 'default', answer: 'granted', registration: fake.registration })
    const result = await enablePush(browser, VAPID)
    expect(browser.requestPermission).toHaveBeenCalledTimes(1)
    expect(result.status).toBe('subscribed')
    expect(result).toMatchObject({ prompted: true })
  })

  it('does not prompt when permission is already granted', async () => {
    const browser = fakeBrowser({ permission: 'granted' })
    const result = await enablePush(browser, VAPID)
    expect(browser.requestPermission).not.toHaveBeenCalled()
    expect(result).toMatchObject({ status: 'subscribed', prompted: false })
  })

  it('never prompts a blocked site', async () => {
    const browser = fakeBrowser({ permission: 'denied' })
    await expect(enablePush(browser, VAPID)).resolves.toEqual({ status: 'blocked' })
    expect(browser.requestPermission).not.toHaveBeenCalled()
    expect(browser.registration).not.toHaveBeenCalled()
  })

  it('reports unsupported without touching the worker', async () => {
    const browser = fakeBrowser({ permission: 'unsupported' })
    await expect(enablePush(browser, VAPID)).resolves.toEqual({ status: 'unsupported' })
    expect(browser.registration).not.toHaveBeenCalled()
  })

  it('tells "Block" from closing the prompt', async () => {
    await expect(enablePush(fakeBrowser({ answer: 'denied' }), VAPID)).resolves.toEqual({ status: 'denied' })
    await expect(enablePush(fakeBrowser({ answer: 'default' }), VAPID)).resolves.toEqual({ status: 'dismissed' })
  })

  it('maps a bad key, a late block and other failures to data, never a throw', async () => {
    await expect(enablePush(fakeBrowser({ permission: 'granted' }), 'not a key')).resolves.toEqual({
      status: 'error',
      reason: 'bad_key',
    })

    const notAllowed = Object.assign(new Error('x'), { name: 'NotAllowedError' })
    const lateBlock = fakeRegistration()
    lateBlock.registration.pushManager.subscribe = vi.fn().mockRejectedValue(notAllowed)
    await expect(
      enablePush(fakeBrowser({ permission: 'granted', registration: lateBlock.registration }), VAPID),
    ).resolves.toEqual({ status: 'denied' })

    await expect(
      enablePush(fakeBrowser({ permission: 'granted', registrationError: new Error('no worker') }), VAPID),
    ).resolves.toEqual({ status: 'error', reason: 'subscribe_failed' })
  })
})

describe('unsubscribeFromPush', () => {
  it('unsubscribes the current subscription', async () => {
    const sub = subscription()
    const result = await unsubscribeFromPush(fakeBrowser({ registration: fakeRegistration(sub).registration }))
    expect(result).toBe(true)
    expect(sub.unsubscribe).toHaveBeenCalled()
  })

  it('is false when there is nothing to remove or no worker', async () => {
    await expect(unsubscribeFromPush(fakeBrowser({}))).resolves.toBe(false)
    await expect(unsubscribeFromPush(fakeBrowser({ registrationError: new Error('x') }))).resolves.toBe(false)
  })
})
