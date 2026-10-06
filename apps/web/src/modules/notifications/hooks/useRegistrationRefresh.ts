import { useQueryClient } from '@tanstack/react-query'
import { useEffect } from 'react'

import { readEnvironment } from '../lib/browser'
import { markSynced, rememberDeviceId } from '../lib/deviceMemory'
import { notificationKeys } from '../lib/keys'
import { syncCurrentDevice } from '../lib/register'
import { peekPushBrowser } from '../lib/serviceWorker'

/**
 * A visit to the settings screen refreshes this browser's record (`last_seen_at`, a rotated endpoint) when alerts are
 * on, then reloads the device list so it shows the result. Silent on failure.
 */
export function useRegistrationRefresh(active: boolean) {
  const qc = useQueryClient()
  useEffect(() => {
    if (!active) return
    let alive = true
    void syncCurrentDevice({ browser: peekPushBrowser, environment: readEnvironment() })
      .then(async (id) => {
        if (!id) return
        rememberDeviceId(id)
        markSynced(Date.now())
        if (alive) await qc.invalidateQueries({ queryKey: notificationKeys.devices })
      })
      .catch(() => undefined)
    return () => {
      alive = false
    }
  }, [active, qc])
}
