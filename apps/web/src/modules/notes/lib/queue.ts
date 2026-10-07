import {
  currentUserId,
  enqueue,
  flushQueue,
  type FlushResult,
  parkedConflicts,
  pending,
  QueuedOffline,
  type QueuedWrite,
  queueStamp,
  removeEntry,
  replay,
  writeOrQueue,
} from '~/lib/offline-queue'

import {
  clipRequest,
  createClip,
  createNote,
  createNoteRequest,
  deleteNote,
  deleteNoteRequest,
  patchNote,
  patchNoteRequest,
  restoreNote,
  restoreNoteRequest,
  setItemTagsRequest,
} from './api'
import { isNotFound, noteConflict, quotaExceeded } from './errors'
import {
  createBodyOf,
  createKey,
  entryNoteId,
  foldCreateBody,
  isCreateEntry,
  patchKey,
  rekeyEntry,
  tagsKey,
} from './local-note'
import {
  clearDraft,
  draftKey,
  markNoteSynced,
  purgeEmptyLocalNotes,
  readCachedNote,
  removeCachedNote,
  renameLocalNote,
} from './offline-store'
import type { Note, NoteConflictDetail, NoteCreate, NotePatch, PatchResult } from './types'

export { createKey, patchKey, tagsKey }

/** The offline lane of notes: it replays in order and never waits on, or blocks, coverage or tracker writes. */
export const NOTES_SCOPE = 'notes'

/** Either the server answered, or the write is stored on this device and will be sent when the network is back. */
export type WriteOutcome<T> = { status: 'saved'; data: T } | { status: 'queued' }

async function outcome<T>(write: Promise<T>): Promise<WriteOutcome<T>> {
  try {
    return { status: 'saved', data: await write }
  } catch (error) {
    if (error instanceof QueuedOffline) return { status: 'queued' }
    throw error
  }
}

type Request = { method: QueuedWrite['method']; path: string; body: Record<string, unknown> }
const queued = (clientId: string, request: Request, label?: string) => ({
  clientId,
  scope: NOTES_SCOPE,
  ...request,
  label,
})

async function waiting(key: string): Promise<QueuedWrite | undefined> {
  const userId = await currentUserId()
  return userId ? (await pending(userId, NOTES_SCOPE)).find((e) => e.clientId === key) : undefined
}

export type CreateFields = Omit<NoteCreate, 'client_id'>
/** `fresh` is false when the text only folded into a create that was already waiting (no new note was made). */
export type CreateOutcome = WriteOutcome<Note> & { fresh: boolean }

/**
 * Creates the row of a note whose id the client chose, with the idempotent `PUT notes/{id}/`. A create that still
 * waits in the queue is updated in place (it keeps its turn, so tags and edits queued after it stay after it).
 */
export async function createNoteOrQueue(id: string, fields: CreateFields, label?: string): Promise<CreateOutcome> {
  const earlier = await waiting(createKey(id))
  if (earlier) {
    await enqueue({ ...earlier, body: foldCreateBody(earlier.body, { ...fields }), label: label ?? earlier.label })
    void flushNotes()
    return { status: 'queued', fresh: false }
  }
  // A full quota is a 429 like a throttle, which the queue would keep and retry. Retrying cannot help a full quota,
  // so it is taken back out of the queue and shown at once (the text stays on this device).
  let refused: unknown
  const result = await outcome(
    writeOrQueue(queued(createKey(id), createNoteRequest(id, fields), label ?? fields.title), () =>
      createNote(id, fields).catch((error: unknown) => {
        if (quotaExceeded(error)) refused = error
        throw error
      }),
    ),
  )
  if (refused) {
    await removeEntry(createKey(id))
    throw refused
  }
  return { ...result, fresh: true }
}

/**
 * Puts the create of a local note in the queue even though the student has not typed yet (they filed it, pinned it or
 * tagged it first). Resolves true when it added one. Later writes of this note are queued behind it.
 */
export async function ensureCreateQueued(note: Note): Promise<boolean> {
  const userId = await currentUserId()
  if (!userId || (await waiting(createKey(note.id)))) return false
  await enqueue({
    ...queued(createKey(note.id), createNoteRequest(note.id, createBodyOf(note)), note.title),
    userId,
    queuedAt: queueStamp(),
  })
  return true
}

/**
 * A tag change on a note the server does not know yet: queued as `PUT items/tags/` behind the create (the newest
 * set replaces the waiting one), because the server can only tag a row that exists.
 */
export async function setNoteTagsAfterCreate(note: Note, tagIds: string[]): Promise<{ createdFresh: boolean }> {
  const createdFresh = await ensureCreateQueued(note)
  const userId = await currentUserId()
  if (userId) {
    const earlier = await waiting(tagsKey(note.id))
    const request = setItemTagsRequest(note.id, tagIds)
    await enqueue(
      earlier
        ? { ...earlier, body: request.body }
        : { ...queued(tagsKey(note.id), request, note.title), userId, queuedAt: queueStamp() },
    )
  }
  void flushNotes()
  return { createdFresh }
}

/** Deleting a note the server never saw forgets its waiting writes: nothing is sent, nothing needs undoing. */
export async function discardLocalNote(userId: string, id: string) {
  const mine = (await pending(userId, NOTES_SCOPE)).filter((e) => entryNoteId(e) === id)
  for (const entry of mine) await removeEntry(entry.clientId)
  await removeCachedNote(userId, id)
  await clearDraft(userId, draftKey(id, '')).catch(() => undefined)
}

export type DeleteOutcome = WriteOutcome<unknown> | { status: 'discarded' }

export async function deleteNoteOrQueue(id: string): Promise<DeleteOutcome> {
  const userId = await currentUserId()
  if (userId && (await readCachedNote(userId, id))?.note.local_only) {
    await discardLocalNote(userId, id)
    return { status: 'discarded' }
  }
  return outcome(
    writeOrQueue(queued(`delete:${id}:${crypto.randomUUID()}`, deleteNoteRequest(id)), () => deleteNote(id)),
  )
}

/** Forgets stale empty local notes (a "New note" tap that was never used). Call before making a new one. */
export async function purgeStaleLocalNotes() {
  const userId = await currentUserId()
  if (!userId) return
  const ids = new Set((await pending(userId, NOTES_SCOPE)).map(entryNoteId).filter((id): id is string => id !== null))
  await purgeEmptyLocalNotes(userId, ids)
}

export const restoreNoteOrQueue = (id: string) =>
  outcome(writeOrQueue(queued(`restore:${id}:${crypto.randomUUID()}`, restoreNoteRequest(id)), () => restoreNote(id)))

export const clipOrQueue = (input: Parameters<typeof createClip>[0]) =>
  outcome(writeOrQueue(queued(input.client_id, clipRequest(input), input.source.label), () => createClip(input)))

/**
 * Folds a newer edit into a waiting one for the same note. The waiting edit keeps its `base_rev` and `base_body_md`
 * (the server still holds that version), the newer fields win, and a `resolution` only ever comes from the newer edit.
 */
export function mergePatchBodies(
  waiting: Record<string, unknown>,
  next: Record<string, unknown>,
): Record<string, unknown> {
  const { resolution: _old, ...rest } = waiting
  const merged: Record<string, unknown> = { ...rest, ...next }
  merged.base_rev = waiting.base_rev ?? next.base_rev
  // `base` holds what the student last saw: the oldest value of each field is the one that counts.
  if (waiting.base !== undefined || next.base !== undefined) {
    merged.base = { ...(next.base as object | undefined), ...(waiting.base as object | undefined) }
  }
  if (waiting.base_body_md !== undefined) merged.base_body_md = waiting.base_body_md
  return merged
}

export async function patchNoteOrQueue(
  id: string,
  patch: NotePatch,
  label?: string,
): Promise<WriteOutcome<PatchResult>> {
  const userId = await currentUserId()
  const waiting = userId ? (await pending(userId, NOTES_SCOPE)).find((e) => e.clientId === patchKey(id)) : undefined
  if (waiting) {
    // Keep the original place in line: an edit must not jump behind a delete queued after it.
    await enqueue({ ...waiting, body: mergePatchBodies(waiting.body, { ...patch }), label: label ?? waiting.label })
    void flushNotes()
    return { status: 'queued' }
  }
  return outcome(writeOrQueue(queued(patchKey(id), patchNoteRequest(id, patch), label), () => patchNote(id, patch)))
}

/** A conflict that left the queue and waits for the student: whose note, what they typed and what the server holds. */
export interface ParkedNoteConflict {
  clientId: string
  noteId: string
  title: string
  detail: NoteConflictDetail
  parkedAt: number
}

const noteIdOf = (path: string) => /\/notes\/([0-9a-f-]{36})\//i.exec(path)?.[1] ?? null

/** Recognises a 409 `note_conflict` on a replayed edit, so the queue parks it instead of dropping it. */
export function parkOnConflict(error: unknown, entry: QueuedWrite) {
  const detail = noteConflict(error)
  const noteId = noteIdOf(entry.path)
  return detail && noteId ? { noteId, detail } : null
}

/** Ids that were replaced during this page's life: their later writes are superseded by the rekeyed ones. */
const replaced = new Map<string, string>()

/** Test hook. */
export const resetReplacedIds = () => replaced.clear()

/**
 * The id of a new note belongs to another student's row (the server answers 404, never saying why). Practically
 * impossible with UUIDs, handled once: the note, its draft and every waiting write move to a fresh id.
 * Resolves with the create to send again (left out of the queue, the caller sends it).
 */
async function rekeyNote(userId: string, entry: QueuedWrite, oldId: string, newId: string): Promise<QueuedWrite> {
  const mine = (await pending(userId, NOTES_SCOPE)).filter((e) => entryNoteId(e) === oldId)
  for (const e of mine) {
    await removeEntry(e.clientId)
    if (e.clientId !== entry.clientId) await enqueue(rekeyEntry(e, oldId, newId))
  }
  await renameLocalNote(userId, oldId, newId)
  replaced.set(oldId, newId)
  return rekeyEntry(entry, oldId, newId)
}

/** The queue's sender for notes: the plain replay, plus what a replayed create needs (flag it synced, or rekey it once). */
export function sendNoteEntry(onRekeyed?: (oldId: string, newId: string) => void) {
  return async (entry: QueuedWrite): Promise<unknown> => {
    const id = entryNoteId(entry)
    if (id && replaced.has(id)) return undefined // superseded: the rekeyed copy of this write is queued
    try {
      const result = await replay(entry)
      if (id && isCreateEntry(entry)) await markNoteSynced(entry.userId, id)
      return result
    } catch (error) {
      if (!(id && isCreateEntry(entry) && isNotFound(error))) throw error
      const newId = crypto.randomUUID()
      const again = await rekeyNote(entry.userId, entry, id, newId)
      onRekeyed?.(id, newId)
      const result = await replay(again) // once: a second refusal drops the create like any other
      await markNoteSynced(entry.userId, newId)
      return result
    }
  }
}

export interface FlushHooks {
  onParked?: (entry: QueuedWrite) => void
  onDropped?: (entry: QueuedWrite, error: unknown) => void
  onRekeyed?: (oldId: string, newId: string) => void
}

export async function flushNotes(hooks: FlushHooks = {}): Promise<FlushResult | null> {
  let rekeyedAny = false
  const run = () =>
    flushQueue({
      scope: NOTES_SCOPE,
      parkOn: parkOnConflict,
      onParked: hooks.onParked,
      onDropped: hooks.onDropped,
      send: sendNoteEntry((oldId, newId) => {
        rekeyedAny = true
        hooks.onRekeyed?.(oldId, newId)
      }),
    })
  const first = await run()
  if (!first || !rekeyedAny) return first
  // The writes of the rekeyed note were re-queued behind the entry being sent: send them now.
  const second = await run()
  return second
    ? { ...first, sent: first.sent + second.sent, dropped: first.dropped + second.dropped, remaining: second.remaining }
    : first
}

export async function parkedNoteConflicts(): Promise<ParkedNoteConflict[]> {
  const userId = await currentUserId()
  if (!userId) return []
  return (await parkedConflicts(userId, NOTES_SCOPE)).map((p) => {
    const detail = p.detail as { noteId: string; detail: NoteConflictDetail }
    return {
      clientId: p.clientId,
      noteId: detail.noteId,
      title: p.entry.label ?? '',
      detail: detail.detail,
      parkedAt: p.parkedAt,
    }
  })
}

export async function queuedNoteWrites(): Promise<QueuedWrite[]> {
  const userId = await currentUserId()
  return userId ? pending(userId, NOTES_SCOPE) : []
}
