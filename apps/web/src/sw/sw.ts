/**
 * The service worker. Compiled by `scripts/build-sw.mjs` into one file served at `/sw.js` (PRD Q5). It does three
 * things only: show push notifications, open the right page when one is clicked, and re-subscribe when the browser
 * rotates the subscription. It has no `fetch` handler, so it never touches or caches a page request.
 * The logic lives in `handlers.ts` and `payload.ts`, which are tested without a worker.
 */
import { urlBase64ToUint8Array } from './applicationServerKey'
import { handleNotificationAction, handleNotificationClick, handlePush, handleSubscriptionChange } from './handlers'
import type {
  ExtendableEventLike,
  NotificationClickEventLike,
  PushEventLike,
  SubscriptionChangeEventLike,
  WorkerScopeLike,
} from './types'

// Replaced by esbuild `define` (see scripts/build-sw.mjs). The fallbacks keep the file valid when it is not built.
declare const __SW_VERSION__: string | undefined
declare const __VAPID_PUBLIC_KEY__: string | undefined
declare const __API_BASE_URL__: string | undefined

const SW_VERSION = typeof __SW_VERSION__ === 'string' && __SW_VERSION__ ? __SW_VERSION__ : 'dev'

function buildKey(): Uint8Array<ArrayBuffer> | null {
  if (typeof __VAPID_PUBLIC_KEY__ !== 'string' || !__VAPID_PUBLIC_KEY__) return null
  try {
    return urlBase64ToUint8Array(__VAPID_PUBLIC_KEY__)
  } catch {
    return null
  }
}

const sw = self as unknown as WorkerScopeLike

/** Typed `addEventListener`: the event classes here are our own small interfaces, so one cast lives in one place. */
const on = <E>(type: string, listener: (event: E) => void) =>
  sw.addEventListener(type, listener as unknown as EventListener)

// Take over on the next load instead of waiting for every old tab to close.
on('install', (event: ExtendableEventLike) => {
  event.waitUntil(sw.skipWaiting())
})

on('activate', (event: ExtendableEventLike) => {
  event.waitUntil(sw.clients.claim())
})

/** The push body as text, or null for an empty push (or one the browser cannot read). */
function pushText(event: PushEventLike): string | null {
  try {
    return event.data ? event.data.text() : null
  } catch {
    return null
  }
}

on('push', (event: PushEventLike) => {
  event.waitUntil(
    handlePush(
      {
        show: (title, options) => sw.registration.showNotification(title, options),
        swVersion: SW_VERSION,
        clients: sw.clients,
      },
      pushText(event),
    ),
  )
})

const API_BASE = typeof __API_BASE_URL__ === 'string' ? __API_BASE_URL__ : ''

on('notificationclick', (event: NotificationClickEventLike) => {
  event.notification.close()
  const deps = { clients: sw.clients, origin: sw.location.origin }
  if (!event.action) {
    event.waitUntil(handleNotificationClick(deps, event.notification.data))
    return
  }
  // A button (W3.6): act through the API and confirm in place; the app opens only from the notification itself.
  event.waitUntil(
    handleNotificationAction(
      {
        ...deps,
        fetch: (url, init) => sw.fetch(url, init),
        apiBase: API_BASE,
        show: (title, options) => sw.registration.showNotification(title, options),
        swVersion: SW_VERSION,
      },
      event.action,
      event.notification.data,
    ),
  )
})

on('pushsubscriptionchange', (event: SubscriptionChangeEventLike) => {
  event.waitUntil(
    handleSubscriptionChange(
      {
        subscribe: (key) => sw.registration.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: key }),
        fallbackKey: buildKey(),
        clients: sw.clients,
      },
      event.oldSubscription,
    ),
  )
})
