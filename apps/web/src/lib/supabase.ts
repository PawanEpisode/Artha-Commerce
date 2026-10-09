import { createClient, type SupabaseClient } from '@supabase/supabase-js'

import { env } from '~/lib/env'

let client: SupabaseClient | null = null

/**
 * The access token from the latest auth event. `undefined` until that event; `null` when signed out.
 * Written synchronously inside `onAuthStateChange` so the first API call after a code does not take the auth lock.
 */
let accessToken: string | null | undefined

export function rememberAccessToken(token: string | null): void {
  accessToken = token
}

export function peekAccessToken(): string | null | undefined {
  return accessToken
}

export const isSupabaseConfigured = Boolean(env.VITE_SUPABASE_URL && env.VITE_SUPABASE_ANON_KEY)

/** Browser Supabase client (auth only). All domain data goes through the Django API. */
export function getSupabase(): SupabaseClient | null {
  if (typeof window === 'undefined' || !isSupabaseConfigured) return null
  const { VITE_SUPABASE_URL: url, VITE_SUPABASE_ANON_KEY: key } = env
  if (!url || !key) return null
  client ??= createClient(url, key, {
    auth: { persistSession: true, autoRefreshToken: true, detectSessionInUrl: true, flowType: 'pkce' },
  })
  return client
}
