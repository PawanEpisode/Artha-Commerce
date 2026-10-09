/** Where to go after auth steps. Keeps redirects on our own site (no open redirect via ?next=). */
export const CONFIRM_TYPES = ['signup', 'invite', 'magiclink', 'recovery', 'email_change', 'email'] as const
export type ConfirmType = (typeof CONFIRM_TYPES)[number]

export const DEFAULT_AFTER_LOGIN = '/app'

export function isConfirmType(value: unknown): value is ConfirmType {
  return typeof value === 'string' && (CONFIRM_TYPES as readonly string[]).includes(value)
}

/** Sign-in and token pages are never a destination. The path is checked without its query, so a nested `?next=` still counts. */
export function isAuthPath(value: string): boolean {
  const cut = value.search(/[?#]/)
  const path = cut === -1 ? value : value.slice(0, cut)
  return path === '/login' || path === '/signup' || path === '/auth' || path.startsWith('/auth/')
}

/** Accepts only same-site absolute paths like `/app/account`. Anything else (`//evil.com`, `https://...`, `javascript:`, `/login`) falls back. */
export function safeNextPath(next: unknown, fallback: string = DEFAULT_AFTER_LOGIN): string {
  if (typeof next !== 'string') return fallback
  if (!next.startsWith('/') || next.startsWith('//') || next.startsWith('/\\')) return fallback
  if ([...next].some((ch) => ch.charCodeAt(0) < 32)) return fallback
  if (isAuthPath(next)) return fallback
  return next
}

/** Destination after a token_hash was verified at /auth/confirm. Recovery and invite must set a password first. */
export function postConfirmPath(type: ConfirmType, next?: string): string {
  switch (type) {
    case 'recovery':
      return '/auth/reset-password'
    case 'invite':
      return '/auth/reset-password?mode=invite'
    case 'email_change':
      return '/app/account'
    default:
      return safeNextPath(next)
  }
}

/** Absolute URL Supabase redirects to after OAuth. */
export function callbackUrl(origin: string, next?: string): string {
  const url = new URL('/auth/callback', origin)
  if (next) url.searchParams.set('next', safeNextPath(next))
  return url.toString()
}
