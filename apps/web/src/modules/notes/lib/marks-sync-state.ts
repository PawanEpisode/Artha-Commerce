import type { SyncState } from '@artha/design-system'

export interface MarksSyncInput {
  online: boolean
  /** A batch is out, or writes wait and the browser is online (they go out at once). */
  saving: boolean
  queued: number
  parked: number
}

/**
 * What the chip in the reader says (PRD 5.3, 7.3). A conflict needs the student first; offline says the marks are safe on
 * this device; online with writes on their way is "Saving"; otherwise "Saved". Unlike notes, writes waiting while online
 * are not "offline": every mark goes through the queue, and the queue is empty again a moment later.
 */
export function deriveMarksSync({ online, saving, queued, parked }: MarksSyncInput): {
  state: SyncState
  count: number
} {
  if (parked > 0) return { state: 'attention', count: parked }
  if (!online) return { state: 'offline', count: queued }
  if (saving || queued > 0) return { state: 'saving', count: 0 }
  return { state: 'saved', count: 0 }
}
