/**
 * Where a notification may take the student. Links are relative paths inside their own workspace. The API checks the
 * same rules when it creates a notification (apps/api/modules/notifications/domain/deeplinks.py); the worker checks
 * again before it opens anything, because a push payload is data from outside the page. `deeplink.test.ts` reads the
 * API file and fails when the two lists drift. Keep one value per line so that test can read them.
 */
export const DEEP_LINK_EXACT_ROUTES: readonly string[] = ['/app']
export const DEEP_LINK_PREFIXES: readonly string[] = [
  '/app/focus',
  '/app/tracker',
  '/app/revision',
  '/app/syllabus',
  '/app/notifications',
  '/app/settings/notifications',
]
export const DEEP_LINK_MAX_LENGTH = 200
/** Where a notification with a missing or refused link opens. */
export const DEFAULT_DEEP_LINK = '/app'

const ENCODED_TRICKS = /%2e|%2f|%5c/i
// eslint-disable-next-line no-control-regex
const CONTROL_CHARS = /[\u0000-\u001f\u007f]/

/** True when `path` is a relative link to an allow-listed page. Never throws. */
export function isAllowedDeepLink(path: unknown): path is string {
  if (typeof path !== 'string' || path.length === 0 || path.length > DEEP_LINK_MAX_LENGTH) return false
  if (!path.startsWith('/') || path.startsWith('//') || path.includes('\\')) return false
  if (CONTROL_CHARS.test(path) || ENCODED_TRICKS.test(path)) return false
  const route = path.split(/[?#]/, 1)[0] ?? ''
  if (route.split('/').some((segment) => segment === '.' || segment === '..')) return false
  const clean = route.replace(/\/+$/, '') || '/'
  return (
    DEEP_LINK_EXACT_ROUTES.includes(clean) || DEEP_LINK_PREFIXES.some((p) => clean === p || clean.startsWith(`${p}/`))
  )
}

/** The link itself when it is allowed, else the default. The query string is kept as sent; nothing is appended. */
export const safeDeepLink = (path: unknown): string => (isAllowedDeepLink(path) ? path : DEFAULT_DEEP_LINK)

/**
 * Absolute URL for `path` on `origin`, or the default page when the link is refused or would leave the origin.
 * The second check is belt and braces: a relative path cannot change origin, but this keeps the guarantee local.
 */
export function resolveDeepLink(path: unknown, origin: string): string {
  const candidate = new URL(safeDeepLink(path), origin)
  return candidate.origin === origin ? candidate.href : new URL(DEFAULT_DEEP_LINK, origin).href
}
