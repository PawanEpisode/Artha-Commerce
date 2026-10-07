/** Shapes of the shared persisted offline queue. */

/** Entries without a scope belong here: the coverage, tracker and focus writes share one ordered lane. */
export const DEFAULT_SCOPE = 'core'

export interface QueuedWrite {
  /** The idempotency key. Also the storage key, so queuing the same write twice keeps one entry. */
  clientId: string
  /** Entries are only replayed for the user who made them. */
  userId: string
  /**
   * The ordered lane the write belongs to (`core`, `notes`, ...). A lane replays in enqueue order and a stuck lane
   * never blocks another one. Missing means `DEFAULT_SCOPE`, which keeps entries queued by older versions valid.
   */
  scope?: string
  method: 'PUT' | 'POST' | 'PATCH' | 'DELETE'
  /** Path under /api/v1, for example /coverage/topics/<id>/. */
  path: string
  body: Record<string, unknown>
  queuedAt: number
  /** Human name of what the write is about (a chapter), only for messages such as "Skipped a mock test for X". */
  label?: string
}

/**
 * A write the server refused because the other side changed too (HTTP 409 with both versions). It leaves the queue so
 * it never blocks the writes behind it, and waits here until the student chooses.
 */
export interface ParkedConflict {
  clientId: string
  userId: string
  scope: string
  entry: QueuedWrite
  /** What the server sent back (their version, device label, time). Opaque to the queue. */
  detail: unknown
  parkedAt: number
}

export const scopeOf = (entry: Pick<QueuedWrite, 'scope'>) => entry.scope ?? DEFAULT_SCOPE
