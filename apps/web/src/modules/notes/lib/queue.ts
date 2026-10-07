import {
  currentUserId,
  enqueue,
  flushQueue,
  type FlushResult,
  parkedConflicts,
  pending,
  QueuedOffline,
  type QueuedWrite,
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
} from './api'
import { noteConflict } from './errors'
import type { Note, NoteConflictDetail, NoteCreate, NotePatch, PatchResult } from './types'

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

export const createNoteOrQueue = (input: NoteCreate): Promise<WriteOutcome<Note>> =>
  outcome(writeOrQueue(queued(input.client_id, createNoteRequest(input), input.title), () => createNote(input)))

export const deleteNoteOrQueue = (id: string) =>
  outcome(writeOrQueue(queued(`delete:${id}:${crypto.randomUUID()}`, deleteNoteRequest(id)), () => deleteNote(id)))

export const restoreNoteOrQueue = (id: string) =>
  outcome(writeOrQueue(queued(`restore:${id}:${crypto.randomUUID()}`, restoreNoteRequest(id)), () => restoreNote(id)))

export const clipOrQueue = (input: Parameters<typeof createClip>[0]) =>
  outcome(writeOrQueue(queued(input.client_id, clipRequest(input), input.source.label), () => createClip(input)))

/** The queue key of a note's pending edit: later edits fold into it instead of piling up. */
export const patchKey = (noteId: string) => `patch:${noteId}`

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

export const flushNotes = (
  hooks: { onParked?: (entry: QueuedWrite) => void; onDropped?: (entry: QueuedWrite, error: unknown) => void } = {},
): Promise<FlushResult | null> =>
  flushQueue({ scope: NOTES_SCOPE, parkOn: parkOnConflict, onParked: hooks.onParked, onDropped: hooks.onDropped })

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
