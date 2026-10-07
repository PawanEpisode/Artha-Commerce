import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from '@tanstack/react-router'
import { useCallback, useEffect, useRef } from 'react'

import type { QueuedWrite } from '~/lib/offline-queue'
import { useOnline } from '~/modules/personalization'

import { notesAnalytics } from '../lib/analytics'
import { quotaExceeded } from '../lib/errors'
import { notesKeys } from '../lib/keys'
import { isCreateEntry } from '../lib/local-note'
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
  const navigate = useNavigate()
  const { queued, oldestQueuedAt } = useNotesQueueState()
  const oldest = useRef(oldestQueuedAt)
  oldest.current = oldestQueuedAt

  const run = useCallback(async () => {
    const dropped: { entry: QueuedWrite; error: unknown }[] = []
    const result = await flushNotes({
      onDropped: (entry, error) => dropped.push({ entry, error }),
      // The note's id was replaced (it collided with another student's): follow it if it is open.
      onRekeyed: (oldId, newId) => {
        if (window.location.pathname.includes(oldId))
          void navigate({ to: '/app/notes/n/$noteId', params: { noteId: newId }, search: {}, replace: true })
      },
    }).catch(() => null)
    if (result && !result.busy) {
      if (result.sent > 0) {
        notify.synced(result.sent)
        notesAnalytics.queueReplayed(result.sent, oldest.current)
      }
      // A note that hit the quota says so as the quota message does; its text stays on this device.
      const quota = dropped.map((d) => (isCreateEntry(d.entry) ? quotaExceeded(d.error) : null)).find(Boolean)
      if (quota) {
        notesAnalytics.quotaBlocked(quota.kind)
        notify.quotaFull(quota.kind)
      }
      const others = dropped.filter((d) => !(isCreateEntry(d.entry) && quotaExceeded(d.error)))
      if (others.length > 0) notify.syncDropped(others.length)
    }
    const changed = result ? result.sent + result.dropped + (result.parked ?? 0) > 0 : false
    // What the server now holds is the truth: refresh every note view the replayed writes touched.
    await qc.invalidateQueries({ queryKey: changed ? notesKeys.all : notesKeys.queue })
    await qc.invalidateQueries({ queryKey: notesKeys.parked })
  }, [qc, navigate])

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
