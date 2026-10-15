import { toast } from '@artha/design-system'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect } from 'react'

import { flushQueue, pendingCount } from '~/lib/offline-queue'
import { ageBucket } from '~/modules/observability'

import { trackToday } from '../lib/analytics'
import { errorCode, TODAY_SCOPE } from '../lib/api'
import { todayKeys } from '../lib/keys'

const POLL_MS = 30_000

/**
 * Replays the changes this device queued (ticks and own tasks) when Today opens, when the browser comes back online and every 30
 * seconds while something waits. Each entry keeps its client id, so a replay never makes a second `done` or a second task. Says
 * "All changes saved" once the queue is empty, and refetches the plan so the server's answer replaces the local copy. Returns how
 * many changes still wait.
 */
export function useTodaySync(enabled: boolean) {
  const qc = useQueryClient()
  const count = useQuery({
    queryKey: todayKeys.offline,
    queryFn: () => pendingCount(TODAY_SCOPE),
    enabled,
    staleTime: 0,
  })
  const waiting = count.data ?? 0

  useEffect(() => {
    if (!enabled) return
    let alive = true
    const sync = async () => {
      const before = Date.now()
      const waitingBefore = await pendingCount(TODAY_SCOPE).catch(() => 0)
      if (waitingBefore === 0) return
      const result = await flushQueue({
        scope: TODAY_SCOPE,
        onDropped: (_entry, error) => {
          const code = errorCode(error)
          toast.info(
            code === 'state_conflict' || code === 'invalid_transition' || code === 'task_not_found'
              ? 'A change you made offline was not applied: the task had changed.'
              : 'A change you made offline could not be saved.',
          )
        },
      }).catch(() => null)
      if (!alive || !result) return
      if (result.sent + result.dropped > 0) {
        trackToday('today_offline_replayed', { count: result.sent, age_bucket: ageBucket(Date.now() - before) })
      }
      if (result.remaining === 0 && !result.busy) {
        if (result.sent > 0) toast.success('All changes saved', { id: 'today-synced' })
        await qc.invalidateQueries({ queryKey: todayKeys.plan }) // the server's plan replaces the local one
      }
      await qc.invalidateQueries({ queryKey: todayKeys.offline })
    }
    void sync()
    window.addEventListener('online', sync)
    return () => {
      alive = false
      window.removeEventListener('online', sync)
    }
  }, [enabled, qc])

  useEffect(() => {
    if (!enabled || waiting === 0) return
    const timer = window.setInterval(() => void qc.invalidateQueries({ queryKey: todayKeys.offline }), POLL_MS)
    return () => window.clearInterval(timer)
  }, [enabled, waiting, qc])

  return { waiting }
}
