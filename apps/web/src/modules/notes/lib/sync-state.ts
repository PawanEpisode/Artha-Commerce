import type { SyncState } from '@artha/design-system'

export interface SyncInput {
  online: boolean
  /** A save is in flight, or text is waiting for the 2 second countdown. */
  saving: boolean
  /** Writes of this account waiting in the offline queue. */
  queued: number
  /** Conflicts parked for the student to settle. */
  parked: number
}

export interface SyncView {
  state: SyncState
  count: number
}

/**
 * What the status chip says. Order matters: a conflict needs the student first; being offline or having writes
 * waiting is next; then saving; otherwise all is saved.
 */
export function deriveSync({ online, saving, queued, parked }: SyncInput): SyncView {
  if (parked > 0) return { state: 'attention', count: parked }
  if (!online || queued > 0) return { state: 'offline', count: queued }
  if (saving) return { state: 'saving', count: 0 }
  return { state: 'saved', count: 0 }
}

/** Next to the chip for a note the server has not confirmed yet (created here, waiting in the queue or still unsent). */
export const UNSYNCED_TEXT = 'Saved on this device, waiting to sync'

/** Say it only once there is something to sync: an empty new note has nothing waiting. */
export const showUnsynced = (
  note: { local_only?: boolean; title: string; body_md: string; tags: readonly unknown[] } | undefined,
) => note?.local_only === true && (note.title.trim() !== '' || note.body_md.trim() !== '' || note.tags.length > 0)
