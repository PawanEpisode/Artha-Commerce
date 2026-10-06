import { useEffect } from 'react'

import { env } from '~/lib/env'
import { useFeatureFlag } from '~/modules/observability'
import { isSubscriptionChangedMessage } from '~/sw/messages'

import { readEnvironment } from '../lib/browser'
import { markSynced, rememberDeviceId, syncedRecently } from '../lib/deviceMemory'
import { RESYNC_MIN_INTERVAL_MS } from '../lib/limits'
import { syncCurrentDevice } from '../lib/register'
import { peekPushBrowser } from '../lib/serviceWorker'

/**
 * Keeps the API's record of this browser current: refreshes it at most twice a day, and straight away when the worker
 * says the browser rotated the subscription (`pushsubscriptionchange`, PRD 5.3). Does nothing, and asks nothing, for a
 * browser that holds no subscription. Failures are silent: the settings screen shows the real state.
 */
export function usePushResync() {
  const enabled = useFeatureFlag('notifications_ui')

  useEffect(() => {
    if (!enabled || !env.VITE_VAPID_PUBLIC_KEY || !('serviceWorker' in navigator)) return

    const run = async (force: boolean) => {
      if (!force && syncedRecently(Date.now(), RESYNC_MIN_INTERVAL_MS)) return
      try {
        const id = await syncCurrentDevice({ browser: peekPushBrowser, environment: readEnvironment() })
        if (id) {
          rememberDeviceId(id)
          markSynced(Date.now())
        }
      } catch {
        // not signed in yet, offline, or the API is off: try again on the next visit
      }
    }

    void run(false)
    const onMessage = (event: MessageEvent) => {
      if (isSubscriptionChangedMessage(event.data)) void run(true)
    }
    navigator.serviceWorker.addEventListener('message', onMessage)
    return () => navigator.serviceWorker.removeEventListener('message', onMessage)
  }, [enabled])
}
