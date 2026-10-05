/**
 * Persisted queue for coverage writes that could not reach the server (FR-30).
 *
 * Only the writes that carry a `client_id` are queued (tick a topic, tick a chapter, log an event). The server
 * ignores a repeated `client_id`, so replaying an entry any number of times (a flush that died half way, two tabs
 * flushing at once) never double counts. Entries live in IndexedDB so they survive a reload or a closed tab, and
 * fall back to memory when IndexedDB is unavailable (private mode, old browsers, SSR).
 */

export interface QueuedWrite {
  /** The idempotency key. Also the storage key, so queuing the same write twice keeps one entry. */
  clientId: string
  /** Entries are only replayed for the user who made them. */
  userId: string
  method: 'PUT' | 'POST'
  /** Path under /api/v1, for example /coverage/topics/<id>/. */
  path: string
  body: Record<string, unknown>
  queuedAt: number
  /** Human name of what the write is about (a chapter), only for messages such as "Skipped a mock test for X". */
  label?: string
}

const DB_NAME = 'artha-coverage'
const STORE = 'writes'
/** A flush gives up on an entry the server keeps rejecting this many times in a row. */
const MAX_ATTEMPTS = 8

interface Backend {
  put: (entry: QueuedWrite) => Promise<void>
  remove: (clientId: string) => Promise<void>
  all: () => Promise<QueuedWrite[]>
  clear: () => Promise<void>
}

function memoryBackend(): Backend {
  const rows = new Map<string, QueuedWrite>()
  return {
    put: async (e) => void rows.set(e.clientId, e),
    remove: async (id) => void rows.delete(id),
    all: async () => [...rows.values()],
    clear: async () => rows.clear(),
  }
}

const wrap = <T>(request: IDBRequest<T>) =>
  new Promise<T>((resolve, reject) => {
    request.onsuccess = () => resolve(request.result)
    request.onerror = () => reject(request.error)
  })

function idbBackend(): Backend {
  let opened: Promise<IDBDatabase> | undefined
  const open = () => {
    opened ??= new Promise<IDBDatabase>((resolve, reject) => {
      const req = indexedDB.open(DB_NAME, 1)
      req.onupgradeneeded = () => req.result.createObjectStore(STORE, { keyPath: 'clientId' })
      req.onsuccess = () => resolve(req.result)
      req.onerror = () => reject(req.error)
      req.onblocked = () => reject(new Error('IndexedDB blocked'))
    })
    return opened
  }
  const store = async (mode: IDBTransactionMode) => (await open()).transaction(STORE, mode).objectStore(STORE)
  return {
    put: async (e) => void (await wrap((await store('readwrite')).put(e))),
    remove: async (id) => void (await wrap((await store('readwrite')).delete(id))),
    all: async () => (await wrap((await store('readonly')).getAll())) as QueuedWrite[],
    clear: async () => void (await wrap((await store('readwrite')).clear())),
  }
}

let backend: Backend | undefined
let fallback: Backend | undefined

/** IndexedDB when there is one; the first failure switches this tab to memory for the rest of its life. */
function current(): Backend {
  if (backend) return backend
  backend = typeof indexedDB === 'undefined' ? (fallback ??= memoryBackend()) : idbBackend()
  return backend
}

async function guarded<T>(run: (b: Backend) => Promise<T>): Promise<T> {
  try {
    return await run(current())
  } catch {
    backend = fallback ??= memoryBackend()
    return run(backend)
  }
}

/** Test hook: forget the opened database so the next call opens a fresh one. */
export function resetOfflineQueue() {
  backend = undefined
  fallback = undefined
}

export const enqueue = (entry: QueuedWrite) => guarded((b) => b.put(entry))

/** The user's pending writes, oldest first. */
export async function pending(userId: string): Promise<QueuedWrite[]> {
  const rows = await guarded((b) => b.all())
  return rows.filter((r) => r.userId === userId).sort((a, b) => a.queuedAt - b.queuedAt)
}

export const clearOfflineQueue = () => guarded((b) => b.clear())

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
}

let flushing: Promise<FlushResult> | undefined
const attempts = new Map<string, number>()

/**
 * Replays the user's queued writes in the order they were made, using the original client ids. Stops at the first
 * transient failure so the order is kept. Concurrent callers share one run.
 */
export function flush(
  userId: string,
  send: (entry: QueuedWrite) => Promise<unknown>,
  onDropped?: DroppedHandler,
): Promise<FlushResult> {
  flushing ??= run(userId, send, onDropped).finally(() => {
    flushing = undefined
  })
  return flushing
}

/** Called for every write the server rejected for good, so the screen can say why (for example target reached). */
export type DroppedHandler = (entry: QueuedWrite, error: unknown) => void

async function run(
  userId: string,
  send: (entry: QueuedWrite) => Promise<unknown>,
  onDropped?: DroppedHandler,
): Promise<FlushResult> {
  const result: FlushResult = { sent: 0, dropped: 0, remaining: 0 }
  const rows = await pending(userId)
  for (const [index, entry] of rows.entries()) {
    try {
      await send(entry)
      await guarded((b) => b.remove(entry.clientId))
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
      // A permanent rejection (or an entry that never succeeds) cannot be fixed by waiting: drop it, keep going.
      await guarded((b) => b.remove(entry.clientId))
      attempts.delete(entry.clientId)
      result.dropped += 1
      onDropped?.(entry, error)
    }
  }
  return result
}
