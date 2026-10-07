/**
 * What the Artha windows of one browser agree on through `localStorage` (X-01 W4.4): who plays the chime for a phase
 * end, and whether any window is visible. Same-origin windows share it, and it is a per-device convenience, so it
 * is read and written in try and catch: where storage throws, every window just behaves as if it were alone.
 */

const ALERT_PREFIX = 'artha:alerted:'
const VISIBLE_PREFIX = 'artha:visible:'
/** Claims older than this are dropped the next time anyone claims. */
const CLAIM_TTL_MS = 24 * 60 * 60 * 1000
/** A visible window re-announces itself this often; a record older than `VISIBLE_TTL_MS` belonged to a window that died. */
export const VISIBLE_REFRESH_MS = 10_000
const VISIBLE_TTL_MS = 25_000

type Store = Pick<Storage, 'getItem' | 'setItem' | 'removeItem' | 'key' | 'length'>

function defaultStore(): Store | null {
  try {
    return typeof window === 'undefined' ? null : window.localStorage
  } catch {
    return null
  }
}

/** The claim key for one alert: the timer and its version at the moment the phase ended (`:target` for the target). */
export const alertClaimKey = (clientId: string, version: number | undefined, kind: 'end' | 'target' = 'end') =>
  `${ALERT_PREFIX}${clientId}:${version ?? 0}${kind === 'target' ? ':target' : ''}`

/**
 * True for the first window to ask about this alert, false for any later one (and for a second hook in the same
 * window), so a chime plays once however many windows are open. With no usable storage it says true: a double chime is
 * better than silence.
 */
export function claimAlert(key: string, now = Date.now(), store: Store | null = defaultStore()): boolean {
  if (!store) return true
  try {
    if (store.getItem(key) !== null) return false
    store.setItem(key, String(now))
    prune(store, now)
    return true
  } catch {
    return true
  }
}

function prune(store: Store, now: number) {
  const stale: string[] = []
  for (let i = 0; i < store.length; i++) {
    const key = store.key(i)
    if (!key?.startsWith(ALERT_PREFIX)) continue
    const at = Number(store.getItem(key))
    if (!Number.isFinite(at) || now - at > CLAIM_TTL_MS) stale.push(key)
  }
  for (const key of stale) store.removeItem(key)
}

/** This window says it is visible now, or that it is not. */
export function reportWindowVisible(
  id: string,
  visible: boolean,
  now = Date.now(),
  store: Store | null = defaultStore(),
) {
  if (!store) return
  try {
    if (visible) store.setItem(VISIBLE_PREFIX + id, String(now))
    else store.removeItem(VISIBLE_PREFIX + id)
  } catch {
    // Not shared: other windows will think this one is hidden, which only means an extra notification.
  }
}

/** Whether a window other than `selfId` said it was visible recently. */
export function otherWindowVisible(selfId: string, now = Date.now(), store: Store | null = defaultStore()): boolean {
  if (!store) return false
  try {
    for (let i = 0; i < store.length; i++) {
      const key = store.key(i)
      if (!key?.startsWith(VISIBLE_PREFIX) || key === VISIBLE_PREFIX + selfId) continue
      const at = Number(store.getItem(key))
      if (Number.isFinite(at) && now - at <= VISIBLE_TTL_MS) return true
    }
  } catch {
    return false
  }
  return false
}

/** One id per page load, so windows tell each other apart. */
export const WINDOW_ID = `w${Math.random().toString(36).slice(2, 10)}`
