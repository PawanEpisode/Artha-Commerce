import { useQueryClient } from '@tanstack/react-query'
import { useCallback, useState } from 'react'

import { currentUserId, resolveParked } from '~/lib/offline-queue'

import { notesAnalytics } from '../lib/analytics'
import { patchNote } from '../lib/api'
import { notesKeys } from '../lib/keys'
import { notify } from '../lib/notify'
import { NOTES_SCOPE, type ParkedNoteConflict } from '../lib/queue'
import type { Resolution } from '../lib/types'
import { storeNote } from './noteCache'
import { useNotesQueueState } from './useNotesSync'

/**
 * Edits the server refused because the note changed elsewhere too (parked by the offline queue). The student settles
 * them one at a time; each choice is sent with the server's revision, then the parked entry is removed.
 */
export function useParkedConflicts() {
  const qc = useQueryClient()
  const { parked } = useNotesQueueState()
  const [busy, setBusy] = useState(false)

  const resolve = useCallback(
    async (conflict: ParkedNoteConflict, resolution: Resolution) => {
      setBusy(true)
      try {
        const { detail } = conflict
        const saved = await patchNote(conflict.noteId, {
          base_rev: detail.theirs.rev,
          title: detail.mine.title ?? detail.theirs.title,
          body_md: detail.mine.body_md ?? detail.theirs.body_md,
          base_body_md: detail.theirs.body_md,
          resolution,
          source: 'manual',
        })
        const userId = await currentUserId()
        if (userId) await resolveParked(conflict.clientId)
        await storeNote(qc, saved)
        notesAnalytics.conflictResolved(resolution)
        notify.conflictResolved()
        await Promise.all([
          qc.invalidateQueries({ queryKey: notesKeys.parked }),
          qc.invalidateQueries({ queryKey: notesKeys.lists }),
        ])
        return true
      } catch (error) {
        notify.error(error, 'Could not settle the conflict. Try again.')
        return false
      } finally {
        setBusy(false)
      }
    },
    [qc],
  )

  return { parked, busy, resolve, scope: NOTES_SCOPE }
}
