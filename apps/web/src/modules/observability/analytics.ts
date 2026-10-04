import posthog from 'posthog-js'
import { useEffect, useState } from 'react'

/** Fire a product analytics event (`noun_verb`). A no-op when PostHog is not configured or not loaded yet. */
export function track(event: string, properties?: Record<string, unknown>) {
  if (typeof window !== 'undefined' && posthog.__loaded) posthog.capture(event, properties)
}

/**
 * Reads a PostHog feature flag. Defaults to ENABLED while flags are unknown (PostHog not configured, still loading,
 * or unreachable), so a flag outage never hides a feature by accident. Only an explicit `false` turns it off.
 */
export function useFeatureFlag(name: string): boolean {
  const [enabled, setEnabled] = useState(true)
  useEffect(() => {
    if (!posthog.__loaded) return
    return posthog.onFeatureFlags(() => setEnabled(posthog.isFeatureEnabled(name) !== false))
  }, [name])
  return enabled
}
