import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useCallback, useEffect, useRef } from 'react'

import type { QueuedWrite } from '~/lib/offline-queue'
import { useOnline } from '~/modules/personalization'

import { notesAnalytics } from '../lib/analytics'
import { notesKeys } from '../lib/keys'
import { notify } from '../lib/notify'
import { flushNotes, parkedNoteConflicts, queuedNoteWrites } from '../lib/queue'
import { deriveSync, type SyncInput, type SyncView } from '../lib/sync-state'

/** What waits on this device: queued writes and parked conflicts. Read only; one flusher (below) does the sending. */
export function useNotesQueueState() {
  const queue = useQuery({ queryKey: notesKeys.queue, queryFn: queuedNoteWrites })
  const parked = useQuery({ queryKey: notesKeys.parked, queryFn: parkedNoteConflicts })
  return {
    queued: queue.data?.length ?? 0,
    oldestQueuedAt: queue.data?.[0]?.queuedAt,
    parked: parked.data ?? [],
  }
}

/** The status chip's state for a screen: online, saving, what waits and what needs the student. */
export function useSyncView(saving: boolean): SyncView {
  const online = useOnline()
  const { queued, parked } = useNotesQueueState()
  const input: SyncInput = { online, saving, queued, parked: parked.length }
  return deriveSync(input)
}

/**
 * Sends the offline queue: when the screen opens, when the browser is back online and every 30 seconds while
 * something waits. Mount it once per notes screen. Only one tab per account sends at a time (Web Locks in the queue).
 */
export function useNotesFlusher(enabled = true) {
  const qc = useQueryClient()
  const { queued, oldestQueuedAt } = useNotesQueueState()
  const oldest = useRef(oldestQueuedAt)
  oldest.current = oldestQueuedAt

  const run = useCallback(async () => {
    const dropped: QueuedWrite[] = []
    const result = await flushNotes({ onDropped: (entry) => dropped.push(entry) }).catch(() => null)
    if (result && !result.busy) {
      if (result.sent > 0) {
        notify.synced(result.sent)
        notesAnalytics.queueReplayed(result.sent, oldest.current)
      }
      if (dropped.length > 0) notify.syncDropped(dropped.length)
    }
    const changed = result ? result.sent + result.dropped + (result.parked ?? 0) > 0 : false
    // What the server now holds is the truth: refresh every note view the replayed writes touched.
    await qc.invalidateQueries({ queryKey: changed ? notesKeys.all : notesKeys.queue })
    await qc.invalidateQueries({ queryKey: notesKeys.parked })
  }, [qc])

  useEffect(() => {
    if (!enabled) return
    void run()
    window.addEventListener('online', run)
    return () => window.removeEventListener('online', run)
  }, [enabled, run])

  useEffect(() => {
    if (!enabled || queued === 0) return
    const timer = window.setInterval(() => void run(), 30_000)
    return () => window.clearInterval(timer)
  }, [enabled, queued, run])

  return { flush: run }
}
