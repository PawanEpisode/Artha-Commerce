import { safeDeepLink } from './deeplink'
import { FALLBACK_TAG, type NotificationContent, parseButtons } from './payload'

/**
 * Buttons on a timer alert (X-01.1 W3.6, FR-N12). A tap sends the button's one-time token to the API, which changes
 * the timer without the app being opened; the answer is a short confirmation that replaces the alert (same tag).
 * Pure helpers here; the worker wiring is in `handlers.ts`.
 */
export const ACTIONS_PATH = '/api/v1/notifications/actions/'

export const UNAVAILABLE_TITLE = 'Open the app'
export const UNAVAILABLE_BODY = 'That button could not be used. Tap to open the app.'

/** Where the worker sends a tap: the API origin baked in at build time, or null when there is none. */
export function actionsUrl(apiBase: string | undefined | null): string | null {
  if (!apiBase) return null
  try {
    const base = new URL(apiBase)
    if (base.protocol !== 'https:' && base.protocol !== 'http:') return null
    return new URL(ACTIONS_PATH, base.origin).toString()
  } catch {
    return null
  }
}

/** The token for one tapped button, read from the notification's data; null when it has none. */
export function tokenFor(data: unknown, action: string): string | null {
  if (!action || typeof data !== 'object' || data === null) return null
  const tokens = (data as { tokens?: unknown }).tokens
  if (typeof tokens !== 'object' || tokens === null) return null
  const token = (tokens as Record<string, unknown>)[action]
  return typeof token === 'string' ? token : null
}

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === 'object' && value !== null && !Array.isArray(value)

const text = (value: unknown, max: number): string => (typeof value === 'string' ? value.trim().slice(0, max) : '')

/**
 * The API's answer to a tap, as something to show. Total: an answer it cannot read becomes the "open the app"
 * notification, keeping the alert's tag and link so it replaces the alert and still leads somewhere useful.
 */
export function parseTapAnswer(answer: unknown, fallback: { tag: string; url: string }): NotificationContent {
  const notification = isRecord(answer) && isRecord(answer.notification) ? answer.notification : null
  const title = notification ? text(notification.title, 120) : ''
  if (!notification || !title) return unavailableContent(fallback)
  const tag =
    typeof notification.tag === 'string' && /^[\w:.-]{1,80}$/.test(notification.tag) ? notification.tag : fallback.tag
  return {
    title,
    body: text(notification.body, 300),
    tag,
    url: safeDeepLink(notification.url ?? fallback.url),
    id: null,
    category: 'timer',
    actions: parseButtons(notification.actions),
  }
}

export function unavailableContent(fallback: { tag: string; url: string }): NotificationContent {
  return {
    title: UNAVAILABLE_TITLE,
    body: UNAVAILABLE_BODY,
    tag: fallback.tag || FALLBACK_TAG,
    url: safeDeepLink(fallback.url),
    id: null,
    category: 'timer',
    actions: [],
  }
}
