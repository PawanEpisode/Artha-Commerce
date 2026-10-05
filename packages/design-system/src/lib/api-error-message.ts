/** Turns a failed API call into one friendly sentence. Duck-typed so the package needs no knowledge of the web app. */

interface ApiErrorLike {
  status: number
  body?: unknown
}

const isApiErrorLike = (e: unknown): e is ApiErrorLike =>
  typeof e === 'object' && e !== null && typeof (e as { status?: unknown }).status === 'number'

/** The API envelope is `{ error: { code, message, details } }`; `details` may hold DRF field errors. */
function envelope(body: unknown): { code?: string; message?: string; details?: unknown } {
  if (typeof body !== 'object' || body === null) return {}
  const err = (body as { error?: unknown }).error
  if (typeof err !== 'object' || err === null) return {}
  const { code, message, details } = err as Record<string, unknown>
  return {
    code: typeof code === 'string' ? code : undefined,
    message: typeof message === 'string' ? message : undefined,
    details,
  }
}

function firstDetail(details: unknown): string | undefined {
  if (typeof details === 'string') return details
  if (Array.isArray(details)) return details.map(firstDetail).find(Boolean)
  if (typeof details === 'object' && details !== null) {
    return Object.values(details).map(firstDetail).find(Boolean)
  }
  return undefined
}

const GENERIC = new Set(['Request failed.', 'Bad request.', 'Invalid input.'])

export function apiErrorMessage(error: unknown, fallback: string): string {
  if (isApiErrorLike(error)) {
    const { message, details } = envelope(error.body)
    const specific = message && !GENERIC.has(message) ? message : firstDetail(details)
    switch (error.status) {
      case 401:
        return 'Your session has ended. Please sign in again.'
      case 403:
        return specific ?? 'You do not have permission to do that.'
      case 404:
        return specific ?? 'We could not find that. It may have been removed.'
      case 429:
        return 'Too many attempts. Wait a moment and try again.'
      default:
        if (error.status >= 500) return 'Something went wrong on our side. Please try again in a moment.'
        return specific ?? fallback
    }
  }
  if (error instanceof TypeError) return 'You seem to be offline. Check your connection and try again.'
  return fallback
}
