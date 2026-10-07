/**
 * The shared persisted offline queue (coverage, tracker, focus and notes). Idempotent writes carrying a client id are
 * stored in IndexedDB and replayed in order per lane (`scope`); a write the server refuses with a two-sided conflict is
 * parked for the student; one tab per account flushes at a time (Web Locks).
 */
export {
  type DroppedHandler,
  flush,
  type FlushOptions,
  type FlushResult,
  isTransient,
  resetFlushState,
  withFlushLock,
} from './flush'
export {
  clearOfflineQueue,
  enqueue,
  parkedConflicts,
  pending,
  removeEntry,
  resetOfflineQueue,
  resolveParked,
} from './store'
export { DEFAULT_SCOPE, type ParkedConflict, type QueuedWrite, scopeOf } from './types'
export { currentUserId, flushQueue, type NewWrite, pendingCount, QueuedOffline, replay, writeOrQueue } from './write'
