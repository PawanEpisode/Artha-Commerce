import { ApiError } from '~/lib/api'

/** One sentence for an API failure: the server's own message when it sent one, else the fallback. */
export function errorText(error: unknown, fallback: string): string {
  if (error instanceof ApiError) {
    const body = error.body as { error?: { message?: unknown; details?: unknown } } | undefined
    const message = body?.error?.message
    if (typeof message === 'string' && message.length > 0 && message.length < 200) return message
    if (error.status === 429) return 'Too many requests. Please wait a moment and try again.'
    if (error.status === 0) return 'You seem to be offline. Try again when you are connected.'
  }
  return fallback
}
