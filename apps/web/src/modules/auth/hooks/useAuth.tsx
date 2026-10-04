import type { Session, User } from '@supabase/supabase-js'
import { createContext, type ReactNode, useContext, useEffect, useMemo, useState } from 'react'

import { getSupabase, isSupabaseConfigured } from '~/lib/supabase'

interface AuthState {
  session: Session | null
  user: User | null
  /** True until the first session lookup finishes. */
  loading: boolean
  configured: boolean
  signInWithGoogle: () => Promise<void>
  signInWithEmail: (email: string) => Promise<{ error?: string }>
  signOut: () => Promise<void>
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
    const redirectTo = () => `${window.location.origin}/auth/callback`
    return {
      session,
      user: session?.user ?? null,
      loading,
      configured: isSupabaseConfigured,
      async signInWithGoogle() {
        await getSupabase()?.auth.signInWithOAuth({ provider: 'google', options: { redirectTo: redirectTo() } })
      },
      async signInWithEmail(email) {
        const supabase = getSupabase()
        if (!supabase) return { error: 'Sign-in is not configured yet.' }
        const { error } = await supabase.auth.signInWithOtp({ email, options: { emailRedirectTo: redirectTo() } })
        return error ? { error: error.message } : {}
      },
      async signOut() {
        await getSupabase()?.auth.signOut()
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
