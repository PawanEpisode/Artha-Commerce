import posthog from 'posthog-js'
import { useEffect, useState } from 'react'

/** Fire a product analytics event (`noun_verb`). A no-op when PostHog is not configured or not loaded yet. */
export function track(event: string, properties?: Record<string, unknown>) {
  if (typeof window !== 'undefined' && posthog.__loaded) posthog.capture(event, properties)
}

/**
 * Reads a PostHog feature flag. Defaults to ENABLED while flags are unknown (PostHog not configured, still loading,
 * or unreachable), so a flag outage never hides a feature by accident. Only an explicit `false` turns it off.
 *
 * `{ strict: true }` is the opposite, for features that cost money or send content to a third party (AI): OFF until PostHog
 * says an explicit `true`, so an outage or a missing key never switches them on. It matches the API's `strict` flag check.
 */
export function useFeatureFlag(name: string, options: { strict?: boolean } = {}): boolean {
  const strict = options.strict === true
  const [enabled, setEnabled] = useState(!strict)
  useEffect(() => {
    if (!posthog.__loaded) return
    return posthog.onFeatureFlags(() => {
      const value = posthog.isFeatureEnabled(name)
      setEnabled(strict ? value === true : value !== false)
    })
  }, [name, strict])
  return enabled
}
