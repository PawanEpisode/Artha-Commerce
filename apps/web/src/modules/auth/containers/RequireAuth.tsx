import { useEffect, type ReactNode } from 'react'
import { useNavigate } from '@tanstack/react-router'
import { useAuth } from '../hooks/useAuth'

/** Client-side route guard. The API independently verifies the JWT, so this is UX, not security. */
export function RequireAuth({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth()
  const navigate = useNavigate()

  useEffect(() => {
    if (!loading && !user) void navigate({ to: '/login' })
  }, [loading, user, navigate])

  if (loading || !user) {
    return <div className="grid min-h-[60vh] place-items-center text-muted-foreground">Loading your workspace…</div>
  }
  return <>{children}</>
}
