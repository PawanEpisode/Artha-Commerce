import type { Fields } from './cardKinds'

/**
 * Edits made offline. One entry per card: a second edit of the same card replaces the first but keeps the version she
 * started from (`baseRev`, `base`), so the merge later still knows what both sides changed. An entry is `waiting` until
 * the connection is back, then it is sent; one the server cannot take on its own becomes `attention` and the student
 * settles it on the card page.
 */
const KEY = 'artha.recall.cardEdits.v1'
export const EDIT_QUEUE_MAX = 50

export type EditAttention =
  { kind: 'conflict'; theirs: Fields; rev: number } | { kind: 'deleted' } | { kind: 'invalid'; message: string }

export interface QueuedEdit {
  cardId: string
  kind: string
  baseRev: number
  base: Fields
  fields: Fields
  importance: 'bullet' | 'important' | 'mandatory'
  tags: string[]
  queuedAt: string
  attention: EditAttention | null
}

function read(userId: string): QueuedEdit[] {
  try {
    const raw = window.localStorage.getItem(`${KEY}.${userId}`)
    const parsed: unknown = raw ? JSON.parse(raw) : []
    return Array.isArray(parsed) ? (parsed as QueuedEdit[]) : []
  } catch {
    return []
  }
}

function write(userId: string, items: QueuedEdit[]): boolean {
  try {
    if (items.length === 0) window.localStorage.removeItem(`${KEY}.${userId}`)
    else window.localStorage.setItem(`${KEY}.${userId}`, JSON.stringify(items))
    return true
  } catch {
    return false
  }
}

export const cardEditQueue = {
  list: read,
  get: (userId: string, cardId: string) => read(userId).find((e) => e.cardId === cardId) ?? null,
  waiting: (userId: string) => read(userId).filter((e) => e.attention === null).length,
  needsAttention: (userId: string) => read(userId).filter((e) => e.attention !== null),
  /** Replaces this card's entry, keeping the version she first started from. */
  put(
    userId: string,
    edit: Omit<QueuedEdit, 'queuedAt' | 'attention'>,
    now = new Date(),
  ): 'queued' | 'full' | 'unsaved' {
    const items = read(userId)
    const existing = items.find((e) => e.cardId === edit.cardId)
    if (!existing && items.length >= EDIT_QUEUE_MAX) return 'full'
    const entry: QueuedEdit = {
      ...edit,
      baseRev: existing?.baseRev ?? edit.baseRev,
      base: existing?.base ?? edit.base,
      queuedAt: now.toISOString(),
      attention: null,
    }
    return write(userId, [...items.filter((e) => e.cardId !== edit.cardId), entry]) ? 'queued' : 'unsaved'
  },
  flag(userId: string, cardId: string, attention: EditAttention) {
    write(
      userId,
      read(userId).map((e) => (e.cardId === cardId ? { ...e, attention } : e)),
    )
  },
  remove(userId: string, cardId: string) {
    write(
      userId,
      read(userId).filter((e) => e.cardId !== cardId),
    )
  },
}
