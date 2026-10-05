import { createFileRoute, useNavigate } from '@tanstack/react-router'
import { useEffect } from 'react'
import { z } from 'zod'

import { safeNextPath, useAuth } from '~/modules/auth'
import { pageHead } from '~/modules/seo'

/** Supabase redirects here after OAuth / magic link. supabase-js exchanges the code automatically. */
export const Route = createFileRoute('/auth/callback')({
  validateSearch: z.object({ next: z.string().optional().catch(undefined) }),
  head: () => pageHead('/auth/callback'),
  component: function Callback() {
    const { next } = Route.useSearch()
    const { user, loading } = useAuth()
    const navigate = useNavigate()
    useEffect(() => {
      if (!loading && user) void navigate({ to: safeNextPath(next), replace: true })
      if (!loading && !user) {
        const t = setTimeout(() => void navigate({ to: '/login', replace: true }), 4000)
        return () => clearTimeout(t)
      }
    }, [loading, user, next, navigate])
    return <div className="grid min-h-[60vh] place-items-center text-muted-foreground">Signing you in…</div>
  },
})
