import type { Session, User } from '@supabase/supabase-js'
import { createContext, type ReactNode, useContext, useEffect, useMemo, useState } from 'react'

import { getSupabase, isSupabaseConfigured } from '~/lib/supabase'

import { notify } from '../lib/notify'
import { callbackUrl } from '../lib/redirects'

interface AuthState {
  session: Session | null
  user: User | null
  /** True until the first session lookup finishes. */
  loading: boolean
  configured: boolean
  signInWithGoogle: (next?: string) => Promise<void>
  /** `silent` skips the "Signed out" toast and ignores a server that no longer knows the student (account deleted). */
  signOut: (options?: { silent?: boolean }) => Promise<void>
}

const AuthContext = createContext<AuthState | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const supabase = getSupabase()
    if (!supabase) {
      setLoading(false)
      return
    }
    supabase.auth.getSession().then(({ data }) => {
      setSession(data.session)
      setLoading(false)
    })
    const { data } = supabase.auth.onAuthStateChange((_event, next) => setSession(next))
    return () => data.subscription.unsubscribe()
  }, [])

  const value = useMemo<AuthState>(() => {
    return {
      session,
      user: session?.user ?? null,
      loading,
      configured: isSupabaseConfigured,
      async signInWithGoogle(next) {
        await getSupabase()?.auth.signInWithOAuth({
          provider: 'google',
          options: { redirectTo: callbackUrl(window.location.origin, next) },
        })
      },
      async signOut(options) {
        if (options?.silent) {
          await getSupabase()
            ?.auth.signOut({ scope: 'local' })
            .catch(() => undefined)
          return
        }
        const { error } = (await getSupabase()?.auth.signOut()) ?? {}
        if (error) notify.failed(error, 'We could not sign you out. Please try again.')
        else notify.signedOut()
      },
    }
  }, [session, loading])

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used inside <AuthProvider>')
  return ctx
}
