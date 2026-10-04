import { createFileRoute, useNavigate } from '@tanstack/react-router'
import { useEffect } from 'react'

import { useAuth } from '~/modules/auth'
import { buildHead } from '~/modules/seo'

/** Supabase redirects here after OAuth / magic link. supabase-js exchanges the code automatically. */
export const Route = createFileRoute('/auth/callback')({
  head: () =>
    buildHead({ title: 'Signing you in', description: 'Signing you in.', path: '/auth/callback', noindex: true }),
  component: function Callback() {
    const { user, loading } = useAuth()
    const navigate = useNavigate()
    useEffect(() => {
      if (!loading && user) void navigate({ to: '/app', replace: true })
      if (!loading && !user) {
        const t = setTimeout(() => void navigate({ to: '/login', replace: true }), 4000)
        return () => clearTimeout(t)
      }
    }, [loading, user, navigate])
    return <div className="grid min-h-[60vh] place-items-center text-muted-foreground">Signing you in…</div>
  },
})
