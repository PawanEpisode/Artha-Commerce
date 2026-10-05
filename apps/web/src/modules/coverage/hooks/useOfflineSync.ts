import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect } from 'react'

import { ruleViolation } from '../lib/api'
import { coverageKeys } from '../lib/keys'
import { notify } from '../lib/notify'
import type { QueuedWrite } from '../lib/offlineQueue'
import { flushQueue, pendingCount } from '../lib/queuedWrites'
import { EVENT_ACTIVITY } from '../lib/rules'
import type { EventType } from '../lib/types'

const key = [...coverageKeys.all, 'offline-queue'] as const

/** What a replayed write that the server refused means for the student: one toast per kind of rejection. */
export function reportFlush(result: { sent: number; dropped: number } | null, refused: Array<[QueuedWrite, unknown]>) {
  if (!result) return
  let skipped = 0
  for (const [entry, error] of refused) {
    const rule = ruleViolation(error)
    const type = entry.body.type as EventType | undefined
    if (rule && (rule.code === 'target_reached' || rule.code === 'activity_not_tracked') && type) {
      notify.queuedLogSkipped(EVENT_ACTIVITY[type], entry.label)
    } else {
      skipped += 1
    }
  }
  if (result.sent > 0) notify.queueSynced(result.sent)
  if (skipped > 0) notify.queueFailed(skipped)
}

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
      const refused: Array<[QueuedWrite, unknown]> = []
      const result = await flushQueue((entry, error) => refused.push([entry, error])).catch(() => null)
      reportFlush(result, refused)
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
    const timer = window.setInterval(() => {
      const refused: Array<[QueuedWrite, unknown]> = []
      void flushQueue((entry, error) => refused.push([entry, error]))
        .then((result) => reportFlush(result, refused))
        .then(() => qc.invalidateQueries({ queryKey: key }))
    }, 30_000)
    return () => window.clearInterval(timer)
  }, [waiting, qc])

  return { pending: waiting, refresh: () => qc.invalidateQueries({ queryKey: key }) }
}
