import { registerLocalDataClearer } from '~/lib/local-data'
import { removeEntry } from '~/lib/offline-queue'

import { clearAnnotationData } from './annotation-store'
import { clearUserData } from './offline-store'
import { queuedNoteWrites } from './queue'

/**
 * Everything the notes module keeps on this device for one student: cached notes and drafts, cached marks of recent
 * PDFs, and writes still waiting to be sent (which would only recreate what was just deleted).
 */
export async function clearNotesLocalData(userId: string): Promise<void> {
  await clearUserData(userId)
  await clearAnnotationData(userId)
  for (const entry of await queuedNoteWrites()) await removeEntry(entry.clientId)
}

registerLocalDataClearer('notes', clearNotesLocalData)
