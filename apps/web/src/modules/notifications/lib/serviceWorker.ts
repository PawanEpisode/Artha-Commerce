import { currentPermission } from './browser'
import type { PushBrowser, PushRegistrationLike } from './push'

export const SW_URL = '/sw.js'
const READY_TIMEOUT_MS = 10_000

/** Production builds always register; development only with `VITE_SW_DEV=true` (PRD W2.4). */
export const shouldAutoRegister = (flags: { production: boolean; swDev: boolean; supported: boolean }): boolean =>
  flags.supported && (flags.production || flags.swDev)

export class ServiceWorkerUnavailable extends Error {
  constructor() {
    super('The service worker did not become ready.')
  }
}

/**
 * Registers `/sw.js` (safe to call again: the browser returns the same registration) and waits for it to be active.
 * `updateViaCache: 'none'` makes the browser fetch `sw.js` fresh on every visit, so a new deploy is picked up at once.
 */
export async function registerServiceWorker(): Promise<ServiceWorkerRegistration> {
  const registration = await navigator.serviceWorker.register(SW_URL, { scope: '/', updateViaCache: 'none' })
  if (registration.active) return registration
  const ready = await Promise.race([
    navigator.serviceWorker.ready,
    new Promise<null>((resolve) => window.setTimeout(() => resolve(null), READY_TIMEOUT_MS)),
  ])
  if (!ready) throw new ServiceWorkerUnavailable()
  return ready
}

/** The real browser, for `enablePush` and friends. */
export const realPushBrowser: PushBrowser = {
  permission: currentPermission,
  requestPermission: () => Notification.requestPermission(),
  registration: () => registerServiceWorker() as Promise<PushRegistrationLike>,
}

/**
 * Like `realPushBrowser`, but never registers anything: it only looks at what exists. For reads (is this browser
 * subscribed?), so merely opening a page does not install a worker.
 */
export const peekPushBrowser: PushBrowser = {
  ...realPushBrowser,
  registration: async () => {
    const existing = await navigator.serviceWorker.getRegistration('/')
    if (!existing) throw new ServiceWorkerUnavailable()
    return existing as PushRegistrationLike
  },
}
