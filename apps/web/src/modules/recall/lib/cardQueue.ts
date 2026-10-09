import type { CreateCardBody } from './api'

/**
 * Cards written offline wait here and are sent when the connection is back. Each carries its `client_id`, so a retry
 * after a dropped response never makes a second card. Local storage is enough for a few dozen small cards; it holds
 * the student's own text only on her device and is cleared as each card is accepted.
 */
const KEY = 'artha.recall.cardQueue.v1'
export const CARD_QUEUE_MAX = 50

export interface QueuedCard {
  body: CreateCardBody
  queuedAt: string
}

function read(userId: string): QueuedCard[] {
  try {
    const raw = window.localStorage.getItem(`${KEY}.${userId}`)
    const parsed: unknown = raw ? JSON.parse(raw) : []
    return Array.isArray(parsed) ? (parsed as QueuedCard[]) : []
  } catch {
    return []
  }
}

function write(userId: string, items: QueuedCard[]): boolean {
  try {
    if (items.length === 0) window.localStorage.removeItem(`${KEY}.${userId}`)
    else window.localStorage.setItem(`${KEY}.${userId}`, JSON.stringify(items))
    return true
  } catch {
    return false
  }
}

export const cardQueue = {
  list: read,
  count: (userId: string) => read(userId).length,
  /** `full` at the limit and `unsaved` when the device refuses to store it: the student is told, nothing is silent. */
  add(userId: string, body: CreateCardBody, now = new Date()): 'queued' | 'full' | 'unsaved' {
    const items = read(userId)
    if (items.some((i) => i.body.client_id === body.client_id)) return 'queued'
    if (items.length >= CARD_QUEUE_MAX) return 'full'
    return write(userId, [...items, { body, queuedAt: now.toISOString() }]) ? 'queued' : 'unsaved'
  },
  remove(userId: string, clientId: string) {
    write(
      userId,
      read(userId).filter((i) => i.body.client_id !== clientId),
    )
  },
}
