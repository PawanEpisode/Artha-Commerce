import { api } from '~/lib/api'
import { getSupabase } from '~/lib/supabase'

import {
  chapterTickRequest,
  eventRequest,
  logEvent,
  newClientId,
  tickChapter,
  tickTopic,
  topicTickRequest,
} from './api'
import {
  type DroppedHandler,
  enqueue,
  flush,
  type FlushResult,
  isTransient,
  pending,
  type QueuedWrite,
} from './offlineQueue'
import type { ChapterState, EventType } from './types'

/** Thrown by `writeOrQueue` when the write was stored for later instead of sent. The caller keeps its optimistic UI. */
export class QueuedOffline extends Error {
  constructor(public entry: QueuedWrite) {
    super('Saved on this device; it will sync when you are back online.')
  }
}

export async function currentUserId(): Promise<string | null> {
  const { data } = (await getSupabase()?.auth.getSession()) ?? { data: { session: null } }
  return data.session?.user.id ?? null
}

const replay = (entry: QueuedWrite) => api(entry.path, { method: entry.method, body: JSON.stringify(entry.body) })

const offline = () => typeof navigator !== 'undefined' && navigator.onLine === false

/**
 * Sends an idempotent write. When the network is down, or an older write of this user is still waiting (so the
 * order of their actions is kept), the write is queued and `QueuedOffline` is thrown. Any other failure (a 4xx)
 * propagates so the screen can roll back.
 */
export async function writeOrQueue<T>(
  entry: Omit<QueuedWrite, 'userId' | 'queuedAt'>,
  send: () => Promise<T>,
): Promise<T> {
  const userId = await currentUserId()
  if (!userId) return send()
  const queued: QueuedWrite = { ...entry, userId, queuedAt: Date.now() }
  if (offline() || (await pending(userId)).length > 0) {
    await enqueue(queued)
    void flushQueue()
    throw new QueuedOffline(queued)
  }
  try {
    return await send()
  } catch (error) {
    if (!isTransient(error)) throw error
    await enqueue(queued)
    throw new QueuedOffline(queued)
  }
}

/** Replays whatever is waiting for the signed-in user. Resolves to null when nobody is signed in. */
export async function flushQueue(onDropped?: DroppedHandler): Promise<FlushResult | null> {
  const userId = await currentUserId()
  return userId && !offline() ? flush(userId, replay, onDropped) : null
}

export async function pendingCount(): Promise<number> {
  const userId = await currentUserId()
  return userId ? (await pending(userId)).length : 0
}

/** Tick (or untick) a topic. Returns null when the write was queued for later. */
export async function tickTopicOrQueue(topicId: string, done: boolean): Promise<ChapterState | null> {
  const id = newClientId()
  const { method, path, body } = topicTickRequest(topicId, done, id)
  return orNull(writeOrQueue({ clientId: id, method, path, body }, () => tickTopic(topicId, done, id)))
}

export async function tickChapterOrQueue(chapterId: string, done: boolean): Promise<ChapterState | null> {
  const id = newClientId()
  const { method, path, body } = chapterTickRequest(chapterId, done, id)
  return orNull(writeOrQueue({ clientId: id, method, path, body }, () => tickChapter(chapterId, done, id)))
}

export async function logEventOrQueue(input: {
  chapter_id: string
  type: EventType
  value?: number | null
  /** Chapter name, kept with a queued write for the "skipped" message. */
  label?: string
}): Promise<ChapterState | null> {
  const id = newClientId()
  const { label, ...fields } = input
  const request = { ...fields, value: input.value ?? null, client_id: id }
  const { method, path, body } = eventRequest(request)
  return orNull(writeOrQueue({ clientId: id, method, path, body, label }, () => logEvent(request)))
}

async function orNull<T>(write: Promise<T>): Promise<T | null> {
  try {
    return await write
  } catch (error) {
    if (error instanceof QueuedOffline) return null
    throw error
  }
}
