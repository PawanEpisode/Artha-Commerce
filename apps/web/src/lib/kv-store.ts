/**
 * A small key-value store over IndexedDB with an in-memory fallback (private mode, old browsers, SSR). For per-device
 * caches and drafts: reads never throw (a failure reads as "nothing stored"), and the first IndexedDB failure switches
 * the tab to memory for the rest of its life, so a screen keeps working even when storage does not.
 */

export interface KvStore<T> {
  get: (key: string) => Promise<T | undefined>
  put: (key: string, value: T) => Promise<void>
  remove: (key: string) => Promise<void>
  all: () => Promise<T[]>
  clear: () => Promise<void>
}

const wrap = <R>(request: IDBRequest<R>) =>
  new Promise<R>((resolve, reject) => {
    request.onsuccess = () => resolve(request.result)
    request.onerror = () => reject(request.error)
  })

export interface KvDatabase {
  /** A typed store inside the database. All stores of a database are created together on first open. */
  store: <T>(name: string) => KvStore<T>
  /** Test hook: drop the open connection and the memory fallback. */
  reset: () => void
}

export function createKvDatabase(dbName: string, version: number, storeNames: readonly string[]): KvDatabase {
  const memory = new Map<string, Map<string, unknown>>(storeNames.map((n) => [n, new Map()]))
  let useMemory = typeof indexedDB === 'undefined'
  let opened: Promise<IDBDatabase> | undefined

  const open = () => {
    opened ??= new Promise<IDBDatabase>((resolve, reject) => {
      const request = indexedDB.open(dbName, version)
      request.onupgradeneeded = () => {
        for (const name of storeNames) {
          if (!request.result.objectStoreNames.contains(name)) request.result.createObjectStore(name)
        }
      }
      request.onsuccess = () => resolve(request.result)
      request.onerror = () => reject(request.error)
      request.onblocked = () => reject(new Error('IndexedDB blocked'))
    })
    return opened
  }

  async function run(
    name: string,
    mode: IDBTransactionMode,
    idb: (store: IDBObjectStore) => IDBRequest,
    mem: (store: Map<string, unknown>) => unknown,
  ): Promise<unknown> {
    if (!useMemory) {
      try {
        const db = await open()
        return await wrap(idb(db.transaction(name, mode).objectStore(name)))
      } catch {
        useMemory = true
      }
    }
    return mem(memory.get(name) ?? new Map())
  }

  return {
    store: <T>(name: string): KvStore<T> => ({
      get: (key) =>
        run(
          name,
          'readonly',
          (s) => s.get(key),
          (m) => m.get(key),
        ) as Promise<T | undefined>,
      put: async (key, value) => {
        await run(
          name,
          'readwrite',
          (s) => s.put(value, key),
          (m) => void m.set(key, value),
        )
      },
      remove: async (key) => {
        await run(
          name,
          'readwrite',
          (s) => s.delete(key),
          (m) => void m.delete(key),
        )
      },
      all: () =>
        run(
          name,
          'readonly',
          (s) => s.getAll(),
          (m) => [...m.values()],
        ) as Promise<T[]>,
      clear: async () => {
        await run(
          name,
          'readwrite',
          (s) => s.clear(),
          (m) => void m.clear(),
        )
      },
    }),
    reset: () => {
      opened = undefined
      useMemory = typeof indexedDB === 'undefined'
      memory.forEach((m) => m.clear())
    },
  }
}
