/**
 * IndexedDB storage for the offline queue and the parked conflicts, with an in-memory fallback when IndexedDB is
 * unavailable (private mode, old browsers, SSR). The first IndexedDB failure switches this tab to memory for the rest
 * of its life, so a write is never lost to a storage error: it just stops surviving a reload.
 */

import { DEFAULT_SCOPE, type ParkedConflict, type QueuedWrite, scopeOf } from './types'

/** The name kept from the first version, which only held coverage writes, so queued entries survive the upgrade. */
const DB_NAME = 'artha-coverage'
const DB_VERSION = 2
const WRITES = 'writes'
const PARKED = 'parked'

interface Backend {
  put: (entry: QueuedWrite) => Promise<void>
  remove: (clientId: string) => Promise<void>
  all: () => Promise<QueuedWrite[]>
  clear: () => Promise<void>
  park: (conflict: ParkedConflict) => Promise<void>
  unpark: (clientId: string) => Promise<void>
  parked: () => Promise<ParkedConflict[]>
}

function memoryBackend(): Backend {
  const rows = new Map<string, QueuedWrite>()
  const conflicts = new Map<string, ParkedConflict>()
  return {
    put: async (e) => void rows.set(e.clientId, e),
    remove: async (id) => void rows.delete(id),
    all: async () => [...rows.values()],
    clear: async () => {
      rows.clear()
      conflicts.clear()
    },
    park: async (c) => void conflicts.set(c.clientId, c),
    unpark: async (id) => void conflicts.delete(id),
    parked: async () => [...conflicts.values()],
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
      const req = indexedDB.open(DB_NAME, DB_VERSION)
      req.onupgradeneeded = () => {
        const db = req.result
        if (!db.objectStoreNames.contains(WRITES)) db.createObjectStore(WRITES, { keyPath: 'clientId' })
        if (!db.objectStoreNames.contains(PARKED)) db.createObjectStore(PARKED, { keyPath: 'clientId' })
      }
      req.onsuccess = () => resolve(req.result)
      req.onerror = () => reject(req.error)
      req.onblocked = () => reject(new Error('IndexedDB blocked'))
    })
    return opened
  }
  const store = async (name: string, mode: IDBTransactionMode) =>
    (await open()).transaction(name, mode).objectStore(name)
  return {
    put: async (e) => void (await wrap((await store(WRITES, 'readwrite')).put(e))),
    remove: async (id) => void (await wrap((await store(WRITES, 'readwrite')).delete(id))),
    all: async () => (await wrap((await store(WRITES, 'readonly')).getAll())) as QueuedWrite[],
    clear: async () => {
      await wrap((await store(WRITES, 'readwrite')).clear())
      await wrap((await store(PARKED, 'readwrite')).clear())
    },
    park: async (c) => void (await wrap((await store(PARKED, 'readwrite')).put(c))),
    unpark: async (id) => void (await wrap((await store(PARKED, 'readwrite')).delete(id))),
    parked: async () => (await wrap((await store(PARKED, 'readonly')).getAll())) as ParkedConflict[],
  }
}

let backend: Backend | undefined
let fallback: Backend | undefined

function current(): Backend {
  if (backend) return backend
  backend = typeof indexedDB === 'undefined' ? (fallback ??= memoryBackend()) : idbBackend()
  return backend
}

export async function guarded<T>(run: (b: Backend) => Promise<T>): Promise<T> {
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
export const removeEntry = (clientId: string) => guarded((b) => b.remove(clientId))
export const clearOfflineQueue = () => guarded((b) => b.clear())

/** The user's pending writes of one lane, oldest first. */
export async function pending(userId: string, scope: string = DEFAULT_SCOPE): Promise<QueuedWrite[]> {
  const rows = await guarded((b) => b.all())
  return rows.filter((r) => r.userId === userId && scopeOf(r) === scope).sort((a, b) => a.queuedAt - b.queuedAt)
}

/** The lanes of one user that still have writes waiting whose name starts with `prefix` (one lane per PDF, for example). */
export async function pendingScopes(userId: string, prefix: string): Promise<string[]> {
  const rows = await guarded((b) => b.all())
  const scopes = new Set(rows.filter((r) => r.userId === userId).map(scopeOf))
  return [...scopes].filter((scope) => scope.startsWith(prefix)).sort()
}

/** Parks a refused write: it leaves the queue and waits for the student's choice. */
export async function parkConflict(conflict: ParkedConflict) {
  await guarded((b) => b.park(conflict))
  await removeEntry(conflict.clientId)
}

/** The user's unresolved conflicts of one lane, oldest first. */
export async function parkedConflicts(userId: string, scope: string): Promise<ParkedConflict[]> {
  const rows = await guarded((b) => b.parked())
  return rows.filter((r) => r.userId === userId && r.scope === scope).sort((a, b) => a.parkedAt - b.parkedAt)
}

/** The conflict is settled (the student chose, or the item is gone). */
export const resolveParked = (clientId: string) => guarded((b) => b.unpark(clientId))
