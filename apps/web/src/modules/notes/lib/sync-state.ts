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
