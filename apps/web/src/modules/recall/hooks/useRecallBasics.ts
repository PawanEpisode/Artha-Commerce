import { useSyncExternalStore } from 'react'

import { useAuth } from '~/modules/auth'
import { useFeatureFlag } from '~/modules/observability'

/**
 * The `recall_system` flag, fail closed: off until PostHog says an explicit `true`, so an outage or a missing key never
 * shows a feature that is not released. It matches the API's strict flag check.
 */
export const useRecallEnabled = () => useFeatureFlag('recall_system', { strict: true })

/** The signed-in student's id, the owner of everything stored on this device. */
export function useRecallUser(): string | null {
  const { session } = useAuth()
  return session?.user.id ?? null
}

const subscribe = (notify: () => void) => {
  window.addEventListener('online', notify)
  window.addEventListener('offline', notify)
  return () => {
    window.removeEventListener('online', notify)
    window.removeEventListener('offline', notify)
  }
}

/** The browser's own idea of being online. It can say yes with no network, so requests still handle failure. */
export function useOnlineStatus(): boolean {
  return useSyncExternalStore(
    subscribe,
    () => navigator.onLine,
    () => true,
  )
}
