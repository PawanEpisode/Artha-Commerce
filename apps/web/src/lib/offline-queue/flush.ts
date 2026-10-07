import { MAX_API_CALLS } from '~/lib/retry'

import { parkConflict, pending, removeEntry } from './store'
import { DEFAULT_SCOPE, type QueuedWrite } from './types'

/** A flush gives up on an entry the server keeps failing this many times in a row (the same cap as every other call). */
const MAX_ATTEMPTS = MAX_API_CALLS

/** Did the request fail for a reason that a later retry can fix (no network, timeout, throttled, server error)? */
export function isTransient(error: unknown): boolean {
  if (error instanceof TypeError) return true // fetch rejects with TypeError when the network is down
  const status = (error as { status?: unknown } | null)?.status
  return typeof status === 'number' && (status === 408 || status === 425 || status === 429 || status >= 500)
}

export interface FlushResult {
  sent: number
  /** Rejected for good by the server (a 4xx): dropped, since retrying cannot help. */
  dropped: number
  /** Still queued. */
  remaining: number
  /** Refused because the other side changed too; waiting for the student's choice. Only present when above zero. */
  parked?: number
  /** Another tab holds the flush lock for this account, so nothing was sent from here. */
  busy?: true
}

/** Called for every write the server rejected for good, so the screen can say why (for example target reached). */
export type DroppedHandler = (entry: QueuedWrite, error: unknown) => void

export interface FlushOptions {
  /** The lane to replay. Defaults to the shared `core` lane. */
  scope?: string
  onDropped?: DroppedHandler
  /**
   * Recognises a refusal that needs the student (a 409 with both versions). Returns what to show, or null for any
   * other error. A recognised write is parked instead of dropped.
   */
  parkOn?: (error: unknown, entry: QueuedWrite) => unknown | null
  onParked?: (entry: QueuedWrite, detail: unknown) => void
}

const running = new Map<string, Promise<FlushResult>>()
const attempts = new Map<string, number>()

/** Test hook. */
export function resetFlushState() {
  running.clear()
  attempts.clear()
}

/**
 * Runs `task` while this tab holds the account's flush lock (Web Locks), so two tabs never replay the same lane at
 * once. Without Web Locks (old browsers, tests) the in-tab guard alone applies. Resolves to null when another tab
 * holds the lock.
 */
export async function withFlushLock<T>(name: string, task: () => Promise<T>): Promise<T | null> {
  const locks = typeof navigator === 'undefined' ? undefined : navigator.locks
  if (!locks) return task()
  return locks.request(name, { ifAvailable: true }, async (lock) => (lock ? task() : null))
}

/**
 * Replays the user's queued writes of one lane in the order they were made, using the original client ids. Stops at
 * the first transient failure so the order is kept. Concurrent callers in this tab share one run; across tabs the Web
 * Locks lock lets one tab flush while the others report `busy`.
 */
export function flush(
  userId: string,
  send: (entry: QueuedWrite) => Promise<unknown>,
  options: FlushOptions = {},
): Promise<FlushResult> {
  const scope = options.scope ?? DEFAULT_SCOPE
  const key = `${userId}:${scope}`
  let run = running.get(key)
  if (!run) {
    run = guardedRun(userId, scope, send, options).finally(() => running.delete(key))
    running.set(key, run)
  }
  return run
}

async function guardedRun(
  userId: string,
  scope: string,
  send: (entry: QueuedWrite) => Promise<unknown>,
  options: FlushOptions,
): Promise<FlushResult> {
  const result = await withFlushLock(`artha-flush:${userId}:${scope}`, () => run(userId, scope, send, options))
  if (result) return result
  return { sent: 0, dropped: 0, remaining: (await pending(userId, scope)).length, busy: true }
}

async function run(
  userId: string,
  scope: string,
  send: (entry: QueuedWrite) => Promise<unknown>,
  options: FlushOptions,
): Promise<FlushResult> {
  const result: FlushResult = { sent: 0, dropped: 0, remaining: 0 }
  const rows = await pending(userId, scope)
  for (const [index, entry] of rows.entries()) {
    try {
      await send(entry)
      await removeEntry(entry.clientId)
      attempts.delete(entry.clientId)
      result.sent += 1
    } catch (error) {
      if (isTransient(error)) {
        const count = (attempts.get(entry.clientId) ?? 0) + 1
        attempts.set(entry.clientId, count)
        if (count < MAX_ATTEMPTS) {
          result.remaining = rows.length - index
          return result
        }
      }
      attempts.delete(entry.clientId)
      const detail = options.parkOn?.(error, entry) ?? null
      if (detail !== null) {
        await parkConflict({ clientId: entry.clientId, userId, scope, entry, detail, parkedAt: Date.now() })
        result.parked = (result.parked ?? 0) + 1
        options.onParked?.(entry, detail)
        continue
      }
      // A permanent rejection (or an entry that never succeeds) cannot be fixed by waiting: drop it, keep going.
      await removeEntry(entry.clientId)
      result.dropped += 1
      options.onDropped?.(entry, error)
    }
  }
  return result
}
