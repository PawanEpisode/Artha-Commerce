/**
 * `?n=<id>` on a deep link (FR-N28): the page tells the API the student opened that notification, then removes the
 * parameter so a refresh or a shared link does not report it again.
 */
export const NOTIFICATION_PARAM = 'n'
const ID_PATTERN = /^[\w-]{1,64}$/

/** The notification id in a query string (`?n=abc`), or null when absent or not shaped like an id. */
export function readNotificationId(search: string): string | null {
  const value = new URLSearchParams(search).get(NOTIFICATION_PARAM)
  return value !== null && ID_PATTERN.test(value) ? value : null
}

/**
 * The same location without `n` (every `n`, in case it repeats), keeping other parameters and the hash. Returns null
 * when there was no `n`, so the caller can skip a pointless history change.
 */
export function withoutNotificationParam(location: { pathname: string; search: string; hash: string }): string | null {
  const params = new URLSearchParams(location.search)
  if (!params.has(NOTIFICATION_PARAM)) return null
  params.delete(NOTIFICATION_PARAM)
  const query = params.toString()
  return `${location.pathname}${query ? `?${query}` : ''}${location.hash}`
}

/**
 * The id present when the app first loaded. The router may rewrite the URL (dropping search keys a route does not
 * declare) before any component runs, so the raw address is read once, as early as possible, and consumed once.
 */
let pending: string | null = null

export function captureLandingId(search: string): void {
  pending = readNotificationId(search) ?? pending
}

export function takeLandingId(): string | null {
  const id = pending
  pending = null
  return id
}

/** Ids already sent in this page's lifetime. A second mount or a strict-mode re-run must not report twice. */
const reported = new Set<string>()

export const alreadyReported = (id: string): boolean => reported.has(id)
export const markReported = (id: string): void => void reported.add(id)
export const resetLandingState = (): void => {
  pending = null
  reported.clear()
}
