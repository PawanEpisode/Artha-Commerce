import { env } from '~/lib/env'
import { getSupabase, peekAccessToken } from '~/lib/supabase'

export class ApiError extends Error {
  /** Seconds the server asks us to wait (429 `Retry-After`), when it said. */
  retryAfter?: number

  constructor(
    public status: number,
    message: string,
    public body?: unknown,
  ) {
    super(message)
  }

  /** The envelope's machine code (`{"error": {"code": ...}}`), when the body has one. */
  get code(): string | undefined {
    const code = (this.body as { error?: { code?: unknown } } | undefined)?.error?.code
    return typeof code === 'string' ? code : undefined
  }
}

const retryAfterOf = (value: string | null): number | undefined => {
  const seconds = Number(value)
  return Number.isFinite(seconds) && seconds > 0 ? seconds : undefined
}

/** The in-memory token when auth has already reported it. Otherwise the session, which takes the auth lock. */
export async function readAccessToken(): Promise<string | undefined> {
  const known = peekAccessToken()
  if (known !== undefined) return known ?? undefined
  const { data } = (await getSupabase()?.auth.getSession()) ?? { data: { session: null } }
  return data.session?.access_token
}

/** Typed fetch wrapper for the Django API. Attaches the Supabase access token automatically. */
export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = await readAccessToken()

  const res = await fetch(`${env.VITE_API_URL}/api/v1${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...init.headers,
    },
  })

  if (!res.ok) {
    const body = await res.json().catch(() => undefined)
    const error = new ApiError(res.status, `API ${res.status} on ${path}`, body)
    error.retryAfter = retryAfterOf(res.headers.get('Retry-After'))
    throw error
  }
  return res.status === 204 ? (undefined as T) : ((await res.json()) as T)
}

/**
 * Unauthenticated read for public pages. Safe to call on the server (SSR loaders): it never touches the session.
 * Returns null for 404 so callers can fall back; other failures throw.
 */
export async function publicApi<T>(path: string): Promise<T | null> {
  const res = await fetch(`${env.VITE_API_URL}/api/v1${path}`, { headers: { Accept: 'application/json' } })
  if (res.status === 404) return null
  if (!res.ok) throw new ApiError(res.status, `API ${res.status} on ${path}`)
  return (await res.json()) as T
}

/**
 * Multipart upload with progress and cancel (fetch cannot report upload progress). The browser sets the multipart
 * boundary itself, so no Content-Type header is sent. Rejects with `ApiError` (status 0 for a network failure) or an
 * `AbortError` when `signal` aborts.
 */
export async function apiUpload<T>(
  path: string,
  form: FormData,
  options: { signal?: AbortSignal; onProgress?: (percent: number) => void } = {},
): Promise<T> {
  const token = await readAccessToken()

  return new Promise<T>((resolve, reject) => {
    const xhr = new XMLHttpRequest()
    xhr.open('POST', `${env.VITE_API_URL}/api/v1${path}`)
    if (token) xhr.setRequestHeader('Authorization', `Bearer ${token}`)
    xhr.responseType = 'json'
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) options.onProgress?.(Math.round((e.loaded / e.total) * 100))
    }
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) return resolve(xhr.response as T)
      const error = new ApiError(xhr.status, `API ${xhr.status} on ${path}`, xhr.response ?? undefined)
      error.retryAfter = retryAfterOf(xhr.getResponseHeader('Retry-After'))
      reject(error)
    }
    xhr.onerror = () => reject(new ApiError(0, `Network error on ${path}`))
    xhr.onabort = () => reject(new DOMException('Upload cancelled', 'AbortError'))
    options.signal?.addEventListener('abort', () => xhr.abort(), { once: true })
    if (options.signal?.aborted) return xhr.abort()
    xhr.send(form)
  })
}
