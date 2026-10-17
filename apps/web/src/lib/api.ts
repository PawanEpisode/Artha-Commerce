import { toast } from '@artha/design-system'

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
    this.name = 'ApiError'
  }

  /** The envelope's machine code (`{"error": {"code": ...}}` or `{"code": ...}`), when the body has one. */
  get code(): string | undefined {
    if (typeof this.body !== 'object' || this.body === null) return undefined
    const b = this.body as Record<string, unknown>
    if (typeof b.error === 'object' && b.error !== null) {
      const c = (b.error as Record<string, unknown>).code
      if (typeof c === 'string') return c
    }
    if (typeof b.code === 'string') return b.code
    return undefined
  }
}

export interface ApiOptions extends RequestInit {
  /** When provided, displays a success toast at the top upon successful response. */
  successMessage?: string
  /** When true, silences automatic toasts for warnings or responses. */
  silent?: boolean
}

const retryAfterOf = (value: string | null): number | undefined => {
  const seconds = Number(value)
  return Number.isFinite(seconds) && seconds > 0 ? seconds : undefined
}

function extractServerMessage(status: number, path: string, body?: unknown): string {
  if (typeof body === 'object' && body !== null) {
    const raw = body as Record<string, unknown>
    const err = typeof raw.error === 'object' && raw.error !== null ? (raw.error as Record<string, unknown>) : raw
    const msg = err.message ?? err.detail
    if (
      typeof msg === 'string' &&
      msg.trim() &&
      !['Request failed.', 'Bad request.', 'Invalid input.'].includes(msg.trim())
    ) {
      return msg.trim()
    }
    const details = err.details !== undefined ? err.details : err !== body ? undefined : raw
    if (typeof details === 'string' && details.trim()) return details.trim()
    if (typeof details === 'object' && details !== null) {
      for (const [key, val] of Object.entries(details)) {
        if (key === 'code' || key === 'status') continue
        if (typeof val === 'string' && val.trim()) return val.trim()
        if (Array.isArray(val) && typeof val[0] === 'string' && val[0].trim()) {
          return val[0].trim()
        }
      }
    }
    if (typeof msg === 'string' && msg.trim()) return msg.trim()
  }
  return `API ${status} on ${path}`
}

function checkResponseWarnings(warningHeader: string | null, body?: unknown) {
  if (warningHeader) {
    toast.warning(warningHeader)
  }
  if (typeof body === 'object' && body !== null) {
    const obj = body as Record<string, unknown>
    if (typeof obj.warning === 'string' && obj.warning.trim()) {
      toast.warning(obj.warning.trim())
    } else if (Array.isArray(obj.warnings)) {
      for (const w of obj.warnings) {
        if (typeof w === 'string' && w.trim()) toast.warning(w.trim())
      }
    }
  }
}

/** The in-memory token when auth has already reported it. Otherwise the session, which takes the auth lock. */
export async function readAccessToken(): Promise<string | undefined> {
  const known = peekAccessToken()
  if (known !== undefined) return known ?? undefined
  const { data } = (await getSupabase()?.auth.getSession()) ?? { data: { session: null } }
  return data.session?.access_token
}

/** Typed fetch wrapper for the Django API. Attaches the Supabase access token automatically. */
export async function api<T>(path: string, init: ApiOptions = {}): Promise<T> {
  const token = await readAccessToken()
  const { successMessage, silent, ...fetchInit } = init

  const res = await fetch(`${env.VITE_API_URL}/api/v1${path}`, {
    ...fetchInit,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...fetchInit.headers,
    },
  })

  if (!res.ok) {
    const body = await res.json().catch(() => undefined)
    const error = new ApiError(res.status, extractServerMessage(res.status, path, body), body)
    error.retryAfter = retryAfterOf(res.headers.get('Retry-After'))
    throw error
  }

  const data =
    res.status === 204 ? (undefined as T) : (((await res.json().catch(() => undefined)) as T) ?? (undefined as T))

  if (!silent) {
    checkResponseWarnings(res.headers.get('x-warning') ?? res.headers.get('warning'), data)
    if (successMessage) {
      toast.success(successMessage)
    }
  }

  return data
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
  options: {
    signal?: AbortSignal
    onProgress?: (percent: number) => void
    successMessage?: string
    silent?: boolean
  } = {},
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
      if (xhr.status >= 200 && xhr.status < 300) {
        if (!options.silent) {
          checkResponseWarnings(xhr.getResponseHeader('x-warning') ?? xhr.getResponseHeader('warning'), xhr.response)
          if (options.successMessage) {
            toast.success(options.successMessage)
          }
        }
        return resolve(xhr.response as T)
      }
      const error = new ApiError(
        xhr.status,
        extractServerMessage(xhr.status, path, xhr.response),
        xhr.response ?? undefined,
      )
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
