import { useLocation, useNavigate } from '@tanstack/react-router'
import { type ReactNode, useEffect } from 'react'

import { useAuth } from '~/modules/auth'
import { useFeatureFlag } from '~/modules/observability'

import { LoadErrorPanel, WorkspaceSkeleton } from '../components/LoadStates'
import { useBootstrap } from '../hooks/useBootstrap'
import { useSlow } from '../hooks/useSlow'
import { rememberCompleted, wasCompleted } from '../lib/completedCache'
import { isOnboardingComplete, ONBOARDING_PATH, onboardingPath } from '../lib/destination'
import { mirrorLandingRedirect } from '../lib/landingRedirect'

/**
 * Gate for everything under /app (PRD 5.1). An unfinished student is sent to onboarding, with the page they asked for
 * kept as `?next=`. Facts, not flags: it asks the server's onboarding state, so it cannot be bypassed by a stale
 * client. If the API is down, a student known to be finished is let through; anyone else gets Retry and Sign out.
 */
export function RequireOnboarded({ children }: { children: ReactNode }) {
  const enabled = useFeatureFlag('personalization')
  const { user, signOut } = useAuth()
  const boot = useBootstrap()
  const navigate = useNavigate()
  const { pathname, href } = useLocation({ select: (l) => ({ pathname: l.pathname, href: l.href }) })
  const onOnboarding = pathname === ONBOARDING_PATH
  const complete = boot.data ? isOnboardingComplete(boot.data) : undefined
  const slow = useSlow(enabled && !onOnboarding && boot.isPending)

  useEffect(() => mirrorLandingRedirect(enabled), [enabled])

  useEffect(() => {
    if (user && complete !== undefined) rememberCompleted(user.id, complete)
  }, [user, complete])

  const mustOnboard = enabled && !onOnboarding && complete === false
  useEffect(() => {
    if (mustOnboard) void navigate({ to: onboardingPath(href), replace: true })
  }, [mustOnboard, navigate, href])

  if (!enabled || onOnboarding || complete) return <>{children}</>
  if (boot.isError) {
    if (user && wasCompleted(user.id)) return <>{children}</>
    return <LoadErrorPanel onRetry={() => void boot.refetch()} onSignOut={() => void signOut()} />
  }
  return <WorkspaceSkeleton slow={slow} />
}
