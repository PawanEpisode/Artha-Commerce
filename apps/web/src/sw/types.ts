/**
 * The few worker types this code touches. The DOM and WebWorker TypeScript libraries cannot be loaded together, so the
 * worker is written against these small interfaces instead. Real browser objects satisfy them; tests pass fakes.
 */
export interface NotificationOptionsLike {
  body: string
  tag: string
  /** Always false: a second push with the same tag replaces the alert quietly (PRD 9.4). */
  renotify: false
  icon: string
  lang: string
  data: NotificationData
  actions?: { action: string; title: string }[]
}

export interface NotificationData {
  url: string
  id: string | null
  category: string | null
  swVersion: string
}

export interface WindowClientLike {
  url: string
  focused: boolean
  visibilityState: 'visible' | 'hidden' | 'prerender' | string
  focus(): Promise<unknown>
  navigate?(url: string): Promise<unknown>
}

export interface ClientsLike {
  matchAll(options: { type: 'window'; includeUncontrolled: boolean }): Promise<readonly WindowClientLike[]>
  openWindow(url: string): Promise<unknown>
  claim(): Promise<void>
}

export interface PushSubscriptionLike {
  options: { applicationServerKey: ArrayBuffer | null }
}

export interface ExtendableEventLike {
  waitUntil(promise: Promise<unknown>): void
}
export interface PushEventLike extends ExtendableEventLike {
  data: { text(): string } | null
}
export interface NotificationClickEventLike extends ExtendableEventLike {
  action: string
  notification: { data: unknown; close(): void }
}
export interface SubscriptionChangeEventLike extends ExtendableEventLike {
  oldSubscription?: PushSubscriptionLike | null
}

export interface WorkerScopeLike extends EventTarget {
  location: { origin: string }
  clients: ClientsLike
  skipWaiting(): Promise<void>
  registration: {
    showNotification(title: string, options: NotificationOptionsLike): Promise<void>
    pushManager: {
      subscribe(options: { userVisibleOnly: true; applicationServerKey: BufferSource }): Promise<unknown>
    }
  }
}
