import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect } from 'react'

import { flushQueue, pendingCount } from '~/lib/offline-queue'

import { trackerKeys } from '../lib/keys'
import { notify } from '../lib/notify'

/** Tells the student what a flush did: how many changes synced and how many the server refused. */
function report(result: Awaited<ReturnType<typeof flushQueue>>) {
  if (result && result.sent > 0) notify.synced(result.sent)
  if (result && result.dropped > 0) notify.syncConflict(result.dropped)
}

/**
 * Flushes the shared offline queue when a tracker screen opens, when the browser comes back online and every 30
 * seconds while something waits. The queue is the one the coverage screens use: each entry replays its own path.
 * Returns how many writes still wait so the screen can say so.
 */
export function useTrackerSync() {
  const qc = useQueryClient()
  const count = useQuery({ queryKey: trackerKeys.offline, queryFn: () => pendingCount() })
  const waiting = count.data ?? 0

  useEffect(() => {
    let alive = true
    const sync = async () => {
      const result = await flushQueue().catch(() => null)
      if (!alive) return
      report(result)
      await qc.invalidateQueries({
        queryKey: result && result.sent + result.dropped > 0 ? trackerKeys.all : trackerKeys.offline,
      })
      if (result && result.sent + result.dropped > 0) await qc.invalidateQueries({ queryKey: ['coverage'] })
    }
    void sync()
    window.addEventListener('online', sync)
    return () => {
      alive = false
      window.removeEventListener('online', sync)
    }
  }, [qc])

  useEffect(() => {
    if (waiting === 0) return
    const timer = window.setInterval(
      () =>
        void flushQueue().then((result) => {
          report(result)
          return qc.invalidateQueries({ queryKey: trackerKeys.offline })
        }),
      30_000,
    )
    return () => window.clearInterval(timer)
  }, [waiting, qc])

  return { pending: waiting, refresh: () => qc.invalidateQueries({ queryKey: trackerKeys.offline }) }
}
