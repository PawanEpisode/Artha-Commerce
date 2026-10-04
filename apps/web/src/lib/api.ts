import { env } from '~/lib/env'
import { getSupabase } from '~/lib/supabase'

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
    public body?: unknown,
  ) {
    super(message)
  }
}

/** Typed fetch wrapper for the Django API. Attaches the Supabase access token automatically. */
export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const { data } = (await getSupabase()?.auth.getSession()) ?? { data: { session: null } }
  const token = data.session?.access_token

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
    throw new ApiError(res.status, `API ${res.status} on ${path}`, body)
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
