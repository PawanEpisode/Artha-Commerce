import { useQueryClient } from '@tanstack/react-query'
import { useCallback } from 'react'

import { currentUserId } from '~/lib/offline-queue'

import { newClientId } from '../lib/api'
import type { LinkSelection } from '../lib/chapter-link'
import { notesKeys } from '../lib/keys'
import { buildLocalNote } from '../lib/local-note'
import { cacheNote, clearDraft, draftKey, saveDraft, unsavedNewDrafts } from '../lib/offline-store'
import { purgeStaleLocalNotes } from '../lib/queue'

export interface StartNoteOptions {
  selection?: LinkSelection | null
  /** Adopt a draft that an older version left on this device (written before notes took a client id). */
  recoverLegacyDraft?: boolean
}

/**
 * Starts a note on this device: the id is made here, the empty note and its filing are written to the local store and
 * the id is returned so the caller can open `/app/notes/n/<id>` at once. No request is made: the row is created on
 * the server by the offline queue after the first save, so the editor works offline from the first keystroke.
 */
export function useStartNote() {
  const qc = useQueryClient()
  return useCallback(
    async ({ selection = null, recoverLegacyDraft = false }: StartNoteOptions = {}): Promise<string> => {
      const id = newClientId()
      const userId = await currentUserId()
      const legacy = userId && recoverLegacyDraft ? (await unsavedNewDrafts(userId))[0] : undefined
      const note = buildLocalNote(id, { selection: legacy?.selection ?? selection })
      qc.setQueryData(notesKeys.note(id), note)
      if (userId) {
        await cacheNote(userId, note, { pending: true })
        if (legacy) {
          // The old text comes back as "Recovered draft": the editor sees a draft that differs from the empty note.
          await saveDraft({
            ...legacy,
            key: draftKey(id, ''),
            noteId: id,
            clientId: id,
            baseRev: 1,
            updatedAt: Date.now(),
          })
          await clearDraft(userId, legacy.key)
        }
        void purgeStaleLocalNotes().catch(() => undefined)
      }
      return id
    },
    [qc],
  )
}
