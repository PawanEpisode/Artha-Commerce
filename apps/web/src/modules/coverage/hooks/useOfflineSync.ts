import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect } from 'react'

import { coverageKeys } from '../lib/keys'
import { flushQueue, pendingCount } from '../lib/queuedWrites'

const key = [...coverageKeys.all, 'offline-queue'] as const

/**
 * Flushes the offline queue when the screen opens, when the browser comes back online and every 30 seconds while
 * something is waiting. Returns how many writes are still waiting so the UI can say so.
 */
export function useOfflineSync() {
  const qc = useQueryClient()
  const count = useQuery({ queryKey: key, queryFn: pendingCount })
  const waiting = count.data ?? 0

  useEffect(() => {
    let alive = true
    const sync = async () => {
      const result = await flushQueue().catch(() => null)
      if (!alive) return
      // What the server now holds is the truth; refresh everything the replayed writes touched.
      await qc.invalidateQueries({ queryKey: result && result.sent + result.dropped > 0 ? coverageKeys.all : key })
    }
    void sync()
    window.addEventListener('online', sync)
    return () => {
      alive = false
      window.removeEventListener('online', sync)
    }
  }, [qc])

  // Retry on a timer only while something is waiting.
  useEffect(() => {
    if (waiting === 0) return
    const timer = window.setInterval(
      () => void flushQueue().then(() => qc.invalidateQueries({ queryKey: key })),
      30_000,
    )
    return () => window.clearInterval(timer)
  }, [waiting, qc])

  return { pending: waiting, refresh: () => qc.invalidateQueries({ queryKey: key }) }
}
