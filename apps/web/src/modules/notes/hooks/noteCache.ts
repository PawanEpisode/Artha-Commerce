import type { QueryClient } from '@tanstack/react-query'

import { currentUserId } from '~/lib/offline-queue'

import { notesKeys } from '../lib/keys'
import { cacheNote, readCachedNote } from '../lib/offline-store'
import { applyLocalEdit, type LocalEdit } from '../lib/optimistic'
import type { Note } from '../lib/types'

/** Keeps one note's three copies in step: the query cache, the offline copy and (when told) the pending flag. */
export async function storeNote(qc: QueryClient, note: Note, pending = false) {
  qc.setQueryData(notesKeys.note(note.id), note)
  const userId = await currentUserId()
  if (userId) await cacheNote(userId, note, { pending })
}

/** The newest local copy of a note: what the screen holds, else what this device cached. */
export async function localNote(qc: QueryClient, id: string): Promise<Note | undefined> {
  const held = qc.getQueryData<Note>(notesKeys.note(id))
  if (held) return held
  const userId = await currentUserId()
  return userId ? (await readCachedNote(userId, id))?.note : undefined
}

/** Shows an edit at once (a write that waits in the offline queue, or one the server has not answered yet). */
export async function applyEditLocally(qc: QueryClient, id: string, edit: LocalEdit, pending: boolean) {
  const note = await localNote(qc, id)
  if (!note) return undefined
  const next = applyLocalEdit(note, edit)
  await storeNote(qc, next, pending)
  return next
}
