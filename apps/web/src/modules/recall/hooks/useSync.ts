import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useCallback, useEffect, useRef, useState } from 'react'

import { trackRecall } from '../lib/analytics'
import { eventStore } from '../lib/eventStore'
import { recallKeys } from '../lib/keys'
import { flush, type FlushResult } from '../lib/sync'
import { useOnlineStatus, useRecallUser } from './useRecallBasics'

export interface SyncState {
  /** Reviews waiting on this device. */
  pending: number
  syncing: boolean
  online: boolean
  /** What the last run did, so the screen can say "3 reviews could not count". */
  last: FlushResult | null
  syncNow: () => Promise<FlushResult | null>
}

/** Seconds between tries while something waits and the last try failed. */
const RETRY_MS = 30_000

/**
 * Sends waiting reviews when a recall screen opens, when the browser comes back online and every 30 seconds while
 * something waits. The sync layer does the work; this hook only schedules it and keeps the counters current.
 */
export function useSync(enabled = true): SyncState {
  const userId = useRecallUser()
  const online = useOnlineStatus()
  const qc = useQueryClient()
  const [syncing, setSyncing] = useState(false)
  const [last, setLast] = useState<FlushResult | null>(null)
  const alive = useRef(true)

  const count = useQuery({
    queryKey: [...recallKeys.offline, userId],
    queryFn: () => (userId ? eventStore.pendingCount(userId) : 0),
    enabled: enabled && userId !== null,
    staleTime: 0,
    // Reads this device's own storage, so it must run offline too (the default would pause it).
    networkMode: 'always',
  })
  const pending = count.data ?? 0

  const syncNow = useCallback(async (): Promise<FlushResult | null> => {
    if (!userId) return null
    setSyncing(true)
    const started = Date.now()
    const result = await flush(userId)
    if (!alive.current) return result
    setSyncing(false)
    setLast(result)
    if (result.sent > 0) {
      trackRecall('recall_sync_completed', {
        events: result.sent,
        merged: result.applied,
        dropped_deleted: result.deleted,
        dropped_stale: result.stale + result.late,
        duration_ms: Date.now() - started,
      })
      void qc.invalidateQueries({ queryKey: recallKeys.today })
      void qc.invalidateQueries({ queryKey: ['recall', 'stats'] })
    }
    void qc.invalidateQueries({ queryKey: recallKeys.offline })
    return result
  }, [userId, qc])

  useEffect(() => {
    alive.current = true
    return () => {
      alive.current = false
    }
  }, [])

  useEffect(() => {
    if (enabled && online && userId) void syncNow()
  }, [enabled, online, userId, syncNow])

  useEffect(() => {
    if (!enabled || !online || pending === 0) return
    const timer = window.setInterval(() => void syncNow(), RETRY_MS)
    return () => window.clearInterval(timer)
  }, [enabled, online, pending, syncNow])

  return { pending, syncing, online, last, syncNow }
}
