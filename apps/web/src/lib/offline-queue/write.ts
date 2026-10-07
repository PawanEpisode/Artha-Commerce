import { api } from '~/lib/api'
import { getSupabase } from '~/lib/supabase'

import { flush, type FlushOptions, type FlushResult, isTransient } from './flush'
import { enqueue, pending } from './store'
import { DEFAULT_SCOPE, type QueuedWrite } from './types'

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

/** The default replay: the entry's own method, path and body, which carries the client id. */
export const replay = (entry: QueuedWrite) =>
  api(entry.path, { method: entry.method, body: entry.method === 'DELETE' ? undefined : JSON.stringify(entry.body) })

const offline = () => typeof navigator !== 'undefined' && navigator.onLine === false

export type NewWrite = Omit<QueuedWrite, 'userId' | 'queuedAt'>

/**
 * Sends an idempotent write. When the network is down, or an older write of this user's lane is still waiting (so the
 * order of their actions is kept), the write is queued and `QueuedOffline` is thrown. Any other failure (a 4xx)
 * propagates so the screen can roll back.
 */
export async function writeOrQueue<T>(entry: NewWrite, send: () => Promise<T>): Promise<T> {
  const userId = await currentUserId()
  if (!userId) return send()
  const scope = entry.scope ?? DEFAULT_SCOPE
  const queued: QueuedWrite = { ...entry, userId, queuedAt: Date.now() }
  if (offline() || (await pending(userId, scope)).length > 0) {
    await enqueue(queued)
    void flushQueue({ scope })
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

/** Replays whatever is waiting in a lane for the signed-in user. Resolves to null when nobody is signed in or offline. */
export async function flushQueue(
  options: FlushOptions & { send?: (entry: QueuedWrite) => Promise<unknown> } = {},
): Promise<FlushResult | null> {
  const userId = await currentUserId()
  if (!userId || offline()) return null
  const { send = replay, ...rest } = options
  return flush(userId, send, rest)
}

export async function pendingCount(scope: string = DEFAULT_SCOPE): Promise<number> {
  const userId = await currentUserId()
  return userId ? (await pending(userId, scope)).length : 0
}
