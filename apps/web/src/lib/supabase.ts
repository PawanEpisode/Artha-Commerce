import { createClient, type SupabaseClient } from '@supabase/supabase-js'

import { env } from '~/lib/env'

let client: SupabaseClient | null = null

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
