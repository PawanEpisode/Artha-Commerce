import { useLocation, useNavigate } from '@tanstack/react-router'
import { type ReactNode, useEffect } from 'react'

import { useAuth } from '../hooks/useAuth'
import { safeNextPath } from '../lib/redirects'

/** Client-side route guard. The API independently verifies the JWT, so this is UX, not security. */
export function RequireAuth({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth()
  const navigate = useNavigate()
  const href = useLocation({ select: (location) => location.href })

  useEffect(() => {
    if (!loading && !user) {
      void navigate({ to: '/login', search: { next: safeNextPath(href) }, replace: true })
    }
  }, [loading, user, navigate, href])

  if (loading || !user) {
    return <div className="grid min-h-[60vh] place-items-center text-muted-foreground">Loading your workspace…</div>
  }
  return <>{children}</>
}
