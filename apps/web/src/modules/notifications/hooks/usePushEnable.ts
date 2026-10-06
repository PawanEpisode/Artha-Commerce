import { useCallback, useRef, useState } from 'react'

import { env } from '~/lib/env'

import { notificationAnalytics } from '../lib/analytics'
import { rememberDeviceId } from '../lib/deviceMemory'
import { enableAlerts, type EnableOutcome } from '../lib/enable'
import type { Environment } from '../lib/platform'
import type { PermissionSource } from '../lib/schemas'
import { realPushBrowser } from '../lib/serviceWorker'

/** Runs the "turn on alerts on this device" flow once at a time and hands back what happened. */
export function usePushEnable(source: PermissionSource) {
  const [busy, setBusy] = useState(false)
  const running = useRef(false)

  const enable = useCallback(
    async (environment: Environment): Promise<EnableOutcome> => {
      const key = env.VITE_VAPID_PUBLIC_KEY
      if (!key) return { status: 'unsupported' }
      if (running.current) return { status: 'dismissed' }
      running.current = true
      setBusy(true)
      try {
        const outcome = await enableAlerts({
          browser: realPushBrowser,
          environment,
          vapidPublicKey: key,
          source,
          analytics: notificationAnalytics,
        })
        if (outcome.status === 'enabled') rememberDeviceId(outcome.deviceId)
        return outcome
      } finally {
        running.current = false
        setBusy(false)
      }
    },
    [source],
  )

  return { enable, busy }
}
