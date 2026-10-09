/**
 * IndexedDB storage for the offline review player: the card pack, the review events waiting to be sent (up to 5,000, in
 * the order they happened) and the sessions in progress. A memory fallback keeps a session working when IndexedDB is
 * unavailable (private mode, SSR); it just stops surviving a reload, like the shared offline queue.
 *
 * This is not the shared `offline-queue` writer: reviews are many, tiny and strictly ordered, and are sent in batches of 100
 * to one endpoint, so they have their own store. Rows hold ids, ratings and times; card text lives only in the pack.
 */

import type { ReviewEventBody } from './api'
import { OFFLINE_EVENT_CAP } from './limits'
import type { ApiPack, ApiQueueCard, ReviewCardPatch } from './schemas'

const DB_NAME = 'artha-recall'
const DB_VERSION = 1
const PACKS = 'packs'
const EVENTS = 'events'
const SESSIONS = 'sessions'
const LOCAL = 'local'

export interface StoredEvent {
  /** The event id: the idempotency key and the storage key, so storing the same review twice keeps one row. */
  id: string
  userId: string
  /** Order of arrival on this device. Events are sent in this order. */
  seq: number
  body: ReviewEventBody
}

export interface StoredPack {
  userId: string
  pack: ApiPack
  /** Device time the pack was stored. The server's own `expires_at` and `generated_at` stay inside `pack`. */
  storedAt: number
}

export interface StoredSession {
  /** The session's id on this device and on the server: the server keeps the client's id. */
  id: string
  userId: string
  source: string
  startedAt: number
  plannedCount: number
  /** The server knows this session. Reviews may carry its id only once this is true on the server, so it is sent first. */
  opened: boolean
  /** The student finished it. The server is told after its reviews have been sent. */
  closed: boolean
  closeSent: boolean
  /** What the session did, kept so the summary screen works when the server has not been reached. */
  summary: LocalSummary | null
}

export interface LocalSummary {
  reviewed: number
  newCards: number
  ratings: { again: number; hard: number; good: number; easy: number }
  activeSeconds: number
}

/** What the player knows about a card that the stored pack does not yet: its state after reviews not yet synced. */
export type LocalMemory = Pick<
  ApiQueueCard,
  | 'state'
  | 'stability'
  | 'difficulty'
  | 'due_scheduled_at'
  | 'postponed_until'
  | 'due_at'
  | 'last_review_at'
  | 'reps'
  | 'lapses'
  | 'step'
>

export interface StoredLocalCard {
  id: string
  userId: string
  memory: LocalMemory
  /** Device time of the last local review of the card. */
  at: number
}

/** Thrown when the device already holds the most events it will keep. The player shows a message and stops adding. */
export class QuotaError extends Error {
  constructor(public readonly limit: number = OFFLINE_EVENT_CAP) {
    super(`This device already holds ${limit} reviews that have not synced.`)
    this.name = 'QuotaError'
  }
}

interface Backend {
  putPack: (row: StoredPack) => Promise<void>
  getPack: (userId: string) => Promise<StoredPack | undefined>
  putEvent: (row: StoredEvent) => Promise<void>
  getEvent: (id: string) => Promise<StoredEvent | undefined>
  countEvents: () => Promise<number>
  removeEvents: (ids: string[]) => Promise<void>
  allEvents: () => Promise<StoredEvent[]>
  putSession: (row: StoredSession) => Promise<void>
  getSession: (id: string) => Promise<StoredSession | undefined>
  allSessions: () => Promise<StoredSession[]>
  putLocal: (row: StoredLocalCard) => Promise<void>
  removeLocal: (ids: string[]) => Promise<void>
  allLocal: () => Promise<StoredLocalCard[]>
  clear: () => Promise<void>
}

function memoryBackend(): Backend {
  const packs = new Map<string, StoredPack>()
  const events = new Map<string, StoredEvent>()
  const sessions = new Map<string, StoredSession>()
  const locals = new Map<string, StoredLocalCard>()
  return {
    putPack: async (r) => void packs.set(r.userId, r),
    getPack: async (u) => packs.get(u),
    putEvent: async (r) => void events.set(r.id, r),
    getEvent: async (id) => events.get(id),
    countEvents: async () => events.size,
    removeEvents: async (ids) => void ids.forEach((id) => events.delete(id)),
    allEvents: async () => [...events.values()],
    putSession: async (r) => void sessions.set(r.id, r),
    getSession: async (id) => sessions.get(id),
    allSessions: async () => [...sessions.values()],
    putLocal: async (r) => void locals.set(r.id, r),
    removeLocal: async (ids) => void ids.forEach((id) => locals.delete(id)),
    allLocal: async () => [...locals.values()],
    clear: async () => {
      packs.clear()
      events.clear()
      sessions.clear()
      locals.clear()
    },
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
        if (!db.objectStoreNames.contains(PACKS)) db.createObjectStore(PACKS, { keyPath: 'userId' })
        if (!db.objectStoreNames.contains(EVENTS)) db.createObjectStore(EVENTS, { keyPath: 'id' })
        if (!db.objectStoreNames.contains(SESSIONS)) db.createObjectStore(SESSIONS, { keyPath: 'id' })
        if (!db.objectStoreNames.contains(LOCAL)) db.createObjectStore(LOCAL, { keyPath: 'id' })
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
    putPack: async (r) => void (await wrap((await store(PACKS, 'readwrite')).put(r))),
    getPack: async (u) => (await wrap((await store(PACKS, 'readonly')).get(u))) as StoredPack | undefined,
    putEvent: async (r) => void (await wrap((await store(EVENTS, 'readwrite')).put(r))),
    getEvent: async (id) => (await wrap((await store(EVENTS, 'readonly')).get(id))) as StoredEvent | undefined,
    countEvents: async () => await wrap((await store(EVENTS, 'readonly')).count()),
    removeEvents: async (ids) => {
      const s = await store(EVENTS, 'readwrite')
      await Promise.all(ids.map((id) => wrap(s.delete(id))))
    },
    allEvents: async () => (await wrap((await store(EVENTS, 'readonly')).getAll())) as StoredEvent[],
    putSession: async (r) => void (await wrap((await store(SESSIONS, 'readwrite')).put(r))),
    getSession: async (id) => (await wrap((await store(SESSIONS, 'readonly')).get(id))) as StoredSession | undefined,
    allSessions: async () => (await wrap((await store(SESSIONS, 'readonly')).getAll())) as StoredSession[],
    putLocal: async (r) => void (await wrap((await store(LOCAL, 'readwrite')).put(r))),
    removeLocal: async (ids) => {
      const st = await store(LOCAL, 'readwrite')
      await Promise.all(ids.map((id) => wrap(st.delete(id))))
    },
    allLocal: async () => (await wrap((await store(LOCAL, 'readonly')).getAll())) as StoredLocalCard[],
    clear: async () => {
      for (const name of [PACKS, EVENTS, SESSIONS, LOCAL]) await wrap((await store(name, 'readwrite')).clear())
    },
  }
}

let lastSeq = 0
let backend: Backend | undefined
let fallback: Backend | undefined

function current(): Backend {
  if (backend) return backend
  backend = typeof indexedDB === 'undefined' ? (fallback ??= memoryBackend()) : idbBackend()
  return backend
}

async function guarded<T>(run: (b: Backend) => Promise<T>): Promise<T> {
  try {
    return await run(current())
  } catch (error) {
    // A full store is an answer, not a storage failure: it must not switch the device to the empty memory fallback
    if (error instanceof QuotaError) throw error
    backend = fallback ??= memoryBackend()
    return run(backend)
  }
}

/** Test hook: forget the opened database so the next call opens a fresh one. */
export function resetEventStore() {
  backend = undefined
  fallback = undefined
  lastSeq = 0
}

/** Packs older than this are shown with a warning: the cards may have changed on another device. */
export const STALE_PACK_MS = 48 * 3_600_000

export const eventStore = {
  /**
   * Stores a pack downloaded from the server. Local card states that the new pack already covers (no waiting events, and
   * older than the pack) are dropped, so the server's copy wins as soon as it has seen the reviews.
   */
  async savePack(userId: string, pack: ApiPack, storedAt = Date.now()): Promise<void> {
    await guarded(async (b) => {
      await b.putPack({ userId, pack, storedAt })
      const waiting = new Set((await b.allEvents()).filter((e) => e.userId === userId).map((e) => e.body.card_id))
      const generated = Date.parse(pack.generated_at)
      const covered = (await b.allLocal())
        .filter(
          (l) => l.userId === userId && !waiting.has(l.id) && l.at <= (Number.isFinite(generated) ? generated : 0),
        )
        .map((l) => l.id)
      if (covered.length) await b.removeLocal(covered)
    })
  },

  /** The stored pack with the states of cards reviewed on this device since, so a second session does not repeat them. */
  async loadPack(userId: string): Promise<StoredPack | undefined> {
    return guarded(async (b) => {
      const row = await b.getPack(userId)
      if (!row) return undefined
      const locals = new Map((await b.allLocal()).filter((l) => l.userId === userId).map((l) => [l.id, l]))
      if (locals.size === 0) return row
      return {
        ...row,
        pack: {
          ...row.pack,
          cards: row.pack.cards.map((c) => {
            const l = locals.get(c.id)
            return l ? { ...c, ...l.memory } : c
          }),
        },
      }
    })
  },

  /**
   * Merges the server's answers about cards (`rev`, state, due time, counts) into the stored pack. A card the server now
   * holds back (suspended, buried, archived) leaves the pack. Memory numbers stay; the next download replaces them.
   */
  async patchPack(userId: string, patches: readonly ReviewCardPatch[]): Promise<void> {
    if (patches.length === 0) return
    await guarded(async (b) => {
      const row = await b.getPack(userId)
      if (!row) return
      const by = new Map(patches.map((p) => [p.id, p]))
      const cards = row.pack.cards.flatMap((c) => {
        const p = by.get(c.id)
        if (!p || p.rev < c.rev) return [c]
        if (p.status !== 'active') return []
        return [{ ...c, rev: p.rev, state: p.state, due_at: p.due_at, reps: p.reps, lapses: p.lapses }]
      })
      await b.putPack({ ...row, pack: { ...row.pack, cards } })
    })
  },

  saveLocalCard: (userId: string, id: string, memory: LocalMemory, at = Date.now()) =>
    guarded((b) => b.putLocal({ id, userId, memory, at })),
  removeLocalCards: (ids: string[]) => guarded((b) => b.removeLocal(ids)),

  /** Adds one event. Storing an id that is already there changes nothing; a full store refuses with `QuotaError`. */
  async addEvent(userId: string, body: ReviewEventBody): Promise<StoredEvent> {
    return guarded(async (b) => {
      const existing = await b.getEvent(body.id)
      if (existing) return existing
      if ((await b.countEvents()) >= OFFLINE_EVENT_CAP) throw new QuotaError()
      if (lastSeq === 0) lastSeq = Math.max(0, ...(await b.allEvents()).map((e) => e.seq))
      lastSeq += 1
      const row: StoredEvent = { id: body.id, userId, seq: lastSeq, body }
      await b.putEvent(row)
      return row
    })
  },

  /** The user's waiting events in the order they happened. */
  async pendingEvents(userId: string): Promise<StoredEvent[]> {
    const all = await guarded((b) => b.allEvents())
    return all.filter((e) => e.userId === userId).sort((a, b) => a.seq - b.seq)
  },
  async pendingCount(userId: string): Promise<number> {
    return (await eventStore.pendingEvents(userId)).length
  },
  removeEvents: (ids: string[]) => guarded((b) => b.removeEvents(ids)),

  saveSession: (row: StoredSession) => guarded((b) => b.putSession(row)),
  getSession: (id: string) => guarded((b) => b.getSession(id)),
  async sessionsFor(userId: string): Promise<StoredSession[]> {
    return (await guarded((b) => b.allSessions())).filter((s) => s.userId === userId)
  },
  clear: () => guarded((b) => b.clear()),
}

/** Whole hours since the pack was stored, for the "downloaded N hours ago" line. */
export const packAgeMs = (row: StoredPack, now = Date.now()) => Math.max(0, now - row.storedAt)
export const isStale = (row: StoredPack, now = Date.now()) => packAgeMs(row, now) > STALE_PACK_MS
