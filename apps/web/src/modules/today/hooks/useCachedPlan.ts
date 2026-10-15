import { useEffect, useState } from 'react'

import { currentUserId } from '~/lib/offline-queue'

import { type CachedPlan, loadCachedPlan } from '../lib/cache'

/**
 * The plan cache of this device: the last plan the student saw, read once on mount. `loaded`
 * is false until the first read finishes, so the screen can tell "no cache" from "not read yet".
 */
export function useCachedPlan(enabled: boolean) {
  const [state, setState] = useState<{ loaded: boolean; userId: string | null; entry: CachedPlan | null }>({
    loaded: false,
    userId: null,
    entry: null,
  })

  useEffect(() => {
    if (!enabled) return
    let alive = true
    void (async () => {
      const userId = await currentUserId().catch(() => null)
      const entry = userId ? await loadCachedPlan(userId) : null
      if (alive) setState({ loaded: true, userId, entry })
    })()
    return () => {
      alive = false
    }
  }, [enabled])

  return state
}
