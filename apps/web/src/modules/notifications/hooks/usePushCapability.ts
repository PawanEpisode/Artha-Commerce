import { useCallback, useEffect, useState } from 'react'

import { env } from '~/lib/env'

import { type BrowserPermission, currentPermission, readEnvironment } from '../lib/browser'
import { derivePermissionView, type PermissionView } from '../lib/permissionView'
import type { Environment } from '../lib/platform'
import { currentSubscription } from '../lib/push'
import { peekPushBrowser } from '../lib/serviceWorker'

interface Snapshot {
  environment: Environment | null
  permission: BrowserPermission
  subscribed: boolean | null
}

const INITIAL: Snapshot = { environment: null, permission: 'default', subscribed: null }

/**
 * What this browser can do about push right now, as one honest view. Re-reads when the student comes back to the tab
 * (they may have just changed the site's permission in the browser) and when the permission changes. Reading never
 * registers a worker or prompts.
 */
export function usePushCapability() {
  const [snapshot, setSnapshot] = useState<Snapshot>(INITIAL)
  const vapidConfigured = Boolean(env.VITE_VAPID_PUBLIC_KEY)

  const refresh = useCallback(async () => {
    const environment = readEnvironment()
    const permission = currentPermission()
    const canHaveSubscription = environment.support === 'supported' && permission === 'granted'
    const subscribed = canHaveSubscription ? (await currentSubscription(peekPushBrowser)) !== null : false
    setSnapshot({ environment, permission, subscribed })
  }, [])

  useEffect(() => {
    void refresh()
    const onVisible = () => {
      if (document.visibilityState === 'visible') void refresh()
    }
    document.addEventListener('visibilitychange', onVisible)
    window.addEventListener('focus', onVisible)

    let status: PermissionStatus | null = null
    let alive = true
    const onChange = () => void refresh()
    void navigator.permissions
      ?.query({ name: 'notifications' })
      .then((result) => {
        if (!alive) return
        status = result
        result.addEventListener('change', onChange)
      })
      .catch(() => undefined)

    return () => {
      alive = false
      document.removeEventListener('visibilitychange', onVisible)
      window.removeEventListener('focus', onVisible)
      status?.removeEventListener('change', onChange)
    }
  }, [refresh])

  const view: PermissionView = derivePermissionView({ ...snapshot, vapidConfigured })
  return { ...snapshot, vapidConfigured, view, refresh }
}
