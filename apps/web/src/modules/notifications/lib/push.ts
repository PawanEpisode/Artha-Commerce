import { InvalidApplicationServerKey, sameKey, urlBase64ToUint8Array } from '~/sw/applicationServerKey'

import type { BrowserPermission } from './browser'
import type { DeviceRegistration } from './schemas'

/** The small slice of the browser's push objects this code uses, so a fake can stand in for it in tests. */
export interface PushSubscriptionLike {
  endpoint: string
  options?: { applicationServerKey: ArrayBuffer | null }
  toJSON(): { endpoint?: string; keys?: Record<string, string | undefined> }
  unsubscribe(): Promise<boolean>
}

export interface PushRegistrationLike {
  pushManager: {
    getSubscription(): Promise<PushSubscriptionLike | null>
    subscribe(options: { userVisibleOnly: true; applicationServerKey: BufferSource }): Promise<PushSubscriptionLike>
  }
}

export interface PushBrowser {
  permission(): BrowserPermission
  requestPermission(): Promise<NotificationPermission>
  /** The active worker's registration; rejects when there is none (see `serviceWorker.ts`). */
  registration(): Promise<PushRegistrationLike>
}

export class IncompleteSubscription extends Error {
  constructor() {
    super('The browser returned a push subscription without its keys.')
  }
}

/** Endpoint and keys in the shape `POST devices/` wants. */
export function toDeviceKeys(subscription: PushSubscriptionLike): Pick<DeviceRegistration, 'endpoint' | 'keys'> {
  const json = subscription.toJSON()
  const endpoint = json.endpoint ?? subscription.endpoint
  const p256dh = json.keys?.p256dh
  const auth = json.keys?.auth
  if (!endpoint || !p256dh || !auth) throw new IncompleteSubscription()
  return { endpoint, keys: { p256dh, auth } }
}

export async function currentSubscription(browser: PushBrowser): Promise<PushSubscriptionLike | null> {
  try {
    return await (await browser.registration()).pushManager.getSubscription()
  } catch {
    return null
  }
}

/**
 * The subscription for our key. An existing one is reused when it was made with the same key; one made with another
 * key (the key was rotated) is dropped first, because the browser refuses to subscribe again with a different key.
 */
export async function subscribeToPush(
  registration: PushRegistrationLike,
  vapidPublicKey: string,
): Promise<PushSubscriptionLike> {
  const key = urlBase64ToUint8Array(vapidPublicKey)
  const existing = await registration.pushManager.getSubscription()
  if (existing) {
    if (sameKey(existing.options?.applicationServerKey, key)) return existing
    await existing.unsubscribe()
  }
  return registration.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: key })
}

export async function unsubscribeFromPush(browser: PushBrowser): Promise<boolean> {
  const subscription = await currentSubscription(browser)
  return subscription ? subscription.unsubscribe() : false
}

export type EnableResult =
  | { status: 'subscribed'; subscription: PushSubscriptionLike; prompted: boolean }
  | { status: 'blocked' }
  | { status: 'denied' }
  | { status: 'dismissed' }
  | { status: 'unsupported' }
  | { status: 'error'; reason: 'bad_key' | 'subscribe_failed' }

const errorName = (error: unknown) => (error instanceof Error ? error.name : '')

/**
 * Asks for permission when it is still undecided (never when it is already blocked), then subscribes.
 * Returns what happened as data, so the caller decides the words and the analytics.
 */
export async function enablePush(browser: PushBrowser, vapidPublicKey: string): Promise<EnableResult> {
  const permission = browser.permission()
  if (permission === 'unsupported') return { status: 'unsupported' }
  if (permission === 'denied') return { status: 'blocked' }

  let prompted = false
  if (permission === 'default') {
    prompted = true
    const answer = await browser.requestPermission()
    if (answer === 'denied') return { status: 'denied' }
    if (answer !== 'granted') return { status: 'dismissed' }
  }

  try {
    const registration = await browser.registration()
    return { status: 'subscribed', subscription: await subscribeToPush(registration, vapidPublicKey), prompted }
  } catch (error) {
    if (error instanceof InvalidApplicationServerKey) return { status: 'error', reason: 'bad_key' }
    // A block that arrived between the prompt and the subscription (policy, or a very fast "Block").
    if (errorName(error) === 'NotAllowedError') return { status: 'denied' }
    return { status: 'error', reason: 'subscribe_failed' }
  }
}
