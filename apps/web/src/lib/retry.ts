import { ApiError } from '~/lib/api'

/** The most calls one request may make, the first included. A failing endpoint is tried at most this many times. */
export const MAX_API_CALLS = 5

const RETRYABLE_CLIENT_ERRORS = new Set([408, 425, 429])

/**
 * Whether a failed read is worth another try (TanStack `retry`; `failureCount` is the number of failures so far).
 * Never past `MAX_API_CALLS`. A 4xx answer is the server's final word (not signed in, switched off, not found,
 * invalid), so repeating it only adds load; timeouts and throttling, 5xx and network failures are retried. A call the
 * page itself cancelled is never retried.
 */
export function shouldRetry(failureCount: number, error: unknown): boolean {
  if (failureCount + 1 >= MAX_API_CALLS) return false
  if (error instanceof DOMException && error.name === 'AbortError') return false
  if (error instanceof ApiError && error.status >= 400 && error.status < 500) {
    return RETRYABLE_CLIENT_ERRORS.has(error.status)
  }
  return true
}

/** Exponential back-off (1 s, 2 s, 4 s, 8 s), or the wait the server asked for when it throttled us. */
export function retryDelay(failureCount: number, error: unknown): number {
  if (error instanceof ApiError && error.retryAfter) return Math.min(error.retryAfter, 30) * 1000
  return Math.min(1000 * 2 ** failureCount, 30_000)
}
