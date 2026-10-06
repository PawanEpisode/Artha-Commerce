import * as Sentry from '@sentry/react'
import { useRouter } from '@tanstack/react-router'
import posthog from 'posthog-js'
import { type ReactNode, useEffect } from 'react'

import { env } from '~/lib/env'
import { useAuth } from '~/modules/auth'

import { useToastAnalytics } from './toastAnalytics'

let initialised = false

function initOnce() {
  if (initialised || typeof window === 'undefined') return
  initialised = true

  if (env.VITE_SENTRY_DSN) {
    Sentry.init({
      dsn: env.VITE_SENTRY_DSN,
      environment: import.meta.env.MODE,
      tracesSampleRate: 0.1,
      replaysOnErrorSampleRate: 0.5,
      integrations: [Sentry.browserTracingIntegration()],
    })
  }

  if (env.VITE_POSTHOG_KEY) {
    posthog.init(env.VITE_POSTHOG_KEY, {
      api_host: env.VITE_POSTHOG_HOST,
      ui_host: env.VITE_POSTHOG_UI_HOST,
      capture_pageview: false, // fired manually on route changes below
      person_profiles: 'identified_only',
      defaults: '2025-05-24',
    })
  }
}

/**
 * Boots Sentry and PostHog once on the client, tracks SPA page views and ties both tools to the signed-in user.
 * Both are no-ops when their env vars are missing, so local dev works without keys.
 */
export function ObservabilityProvider({ children }: { children: ReactNode }) {
  const router = useRouter()
  const { user } = useAuth()
  useToastAnalytics()

  useEffect(() => {
    initOnce()
    const track = () => posthog.__loaded && posthog.capture('$pageview')
    track()
    return router.subscribe('onResolved', ({ pathChanged }) => {
      if (pathChanged) track()
    })
  }, [router])

  useEffect(() => {
    if (user) {
      if (posthog.__loaded) posthog.identify(user.id, { email: user.email })
      Sentry.setUser({ id: user.id })
    } else {
      if (posthog.__loaded) posthog.reset()
      Sentry.setUser(null)
    }
  }, [user])

  return <>{children}</>
}

export const captureException = Sentry.captureException
