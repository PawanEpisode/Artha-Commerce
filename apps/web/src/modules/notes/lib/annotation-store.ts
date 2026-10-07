import { createKvDatabase } from '~/lib/kv-store'

import type { MarkRecord, MarksInfo } from './annotation-types'
import { pickEvictions } from './offline-store'

/**
 * Per-device copy of the marks of the last three documents the student opened (FR-F03-63), tombstones included, with the
 * `change_seq` the delta feed resumes from. Marks that were made here and are still waiting in the queue are rebuilt
 * from the queue on load, so this cache is a speed-up, never the only place a write lives. Keyed by user.
 */

/** How many documents keep their marks for offline reading. */
export const RECENT_DOCUMENTS = 3

const db = createKvDatabase('artha-annotations', 1, ['documents'])
const documents = db.store<CachedMarks>('documents')

export interface CachedMarks {
  userId: string
  documentId: string
  marks: MarkRecord[]
  /** The delta feed resumes after this `seq` (`next_since_seq` of the last page; never a write's own `change_seq`). */
  sinceSeq: number
  /** When the feed last caught up, ms. Null before the first delta. */
  syncedAt: number | null
  openedAt: number
  marksInfo: MarksInfo | null
}

const cacheKey = (userId: string, documentId: string) => `${userId}:${documentId}`

export async function readCachedMarks(userId: string, documentId: string): Promise<CachedMarks | undefined> {
  const found = await documents.get(cacheKey(userId, documentId))
  return found?.userId === userId ? found : undefined
}

export async function writeCachedMarks(entry: CachedMarks) {
  await documents.put(cacheKey(entry.userId, entry.documentId), entry)
  const mine = (await documents.all()).filter((e) => e.userId === entry.userId)
  for (const index of pickEvictions(
    mine.map((e) => ({ lastOpenedAt: e.openedAt })),
    RECENT_DOCUMENTS,
  )) {
    const evicted = mine[index]
    if (evicted) await documents.remove(cacheKey(evicted.userId, evicted.documentId))
  }
}

/** Forget everything kept for this user (account deletion, "Delete all my notes"). */
export async function clearAnnotationData(userId: string) {
  for (const entry of await documents.all())
    if (entry.userId === userId) await documents.remove(cacheKey(userId, entry.documentId))
}

export const resetAnnotationStore = () => db.reset()

// ---- Device id ---------------------------------------------------------------------------------------------------------

const DEVICE_KEY = 'artha.notes.device-id'
let memoryDeviceId: string | null = null

/**
 * A random id per browser install (not a fingerprint), sent with each mark so a conflict can say "edited on 3f2b8c1e".
 * Falls back to one per page load when storage is blocked.
 */
export function deviceId(): string {
  try {
    const existing = window.localStorage.getItem(DEVICE_KEY)
    if (existing && existing.length <= 36) return existing
    const fresh = crypto.randomUUID()
    window.localStorage.setItem(DEVICE_KEY, fresh)
    return fresh
  } catch {
    return (memoryDeviceId ??= crypto.randomUUID())
  }
}
