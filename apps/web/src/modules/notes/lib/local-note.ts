import type { QueuedWrite } from '~/lib/offline-queue'

import { linkFromSelection, type LinkSelection } from './chapter-link'
import type { Note, NoteCreate } from './types'

/**
 * Notes that start on this device. The client generates the note id, so the editor opens at once and works offline
 * from the first keystroke; the offline queue creates the row later with an idempotent `PUT notes/{id}/`.
 * Everything here is pure (no storage, no network) so the rules are unit tested.
 */

/** The queue keys of one note's writes. A key is both the idempotency key and the storage key, so each stays single. */
export const createKey = (noteId: string) => `create:${noteId}`
export const tagsKey = (noteId: string) => `tags:${noteId}`
export const patchKey = (noteId: string) => `patch:${noteId}`

export interface LocalNoteSeed {
  /** Where the note starts out filed (a chapter page, `?chapter=`). */
  selection?: LinkSelection | null
}

/** The note as this device holds it before the server knows it. `rev` is 1 because that is what the create produces. */
export function buildLocalNote(id: string, seed: LocalNoteSeed = {}, now: string = new Date().toISOString()): Note {
  return {
    id,
    kind: 'note',
    origin: 'typed',
    title: '',
    snippet: '',
    body_chars: 0,
    pinned: false,
    is_current_summary: false,
    link: linkFromSelection(seed.selection ?? null),
    tags: [],
    rev: 1,
    created_at: now,
    updated_at: now,
    deleted_at: null,
    purge_after: null,
    client_id: id,
    body_md: '',
    lang: 'en',
    clip_source: null,
    image_ids: [],
    local_only: true,
  }
}

/** Has the student put anything into this local note (text, a title, a tag)? An empty one is never sent. */
export const hasContent = (note: Pick<Note, 'title' | 'body_md' | 'tags'>) =>
  note.title.trim() !== '' || note.body_md.trim() !== '' || note.tags.length > 0

/** The create body that says what the local note holds now. */
export const createBodyOf = (note: Note): Omit<NoteCreate, 'client_id'> => ({
  title: note.title,
  body_md: note.body_md,
  chapter_id: note.link.chapter_id,
  topic_id: note.link.topic_id,
})

/** Newer fields win; `undefined` never erases what the waiting create already says. The client id stays. */
export function foldCreateBody(
  waiting: Record<string, unknown>,
  next: Record<string, unknown>,
): Record<string, unknown> {
  const merged: Record<string, unknown> = { ...waiting }
  for (const [key, value] of Object.entries(next)) if (value !== undefined && key !== 'client_id') merged[key] = value
  return merged
}

const NOTE_PATH = /^\/notes\/([0-9a-f-]{36})\/$/i

/** Which note a queued write belongs to: its path (create, edit, delete) or its body (tags). */
export function entryNoteId(entry: Pick<QueuedWrite, 'path' | 'body' | 'clientId'>): string | null {
  const fromPath = NOTE_PATH.exec(entry.path)?.[1]
  if (fromPath) return fromPath
  return typeof entry.body.item_id === 'string' ? entry.body.item_id : null
}

export const isCreateEntry = (entry: Pick<QueuedWrite, 'method' | 'path' | 'clientId'>) =>
  entry.method === 'PUT' && entry.clientId.startsWith('create:')

/** The entry as it must be sent once the note has a new id: key, path and the ids in the body follow the note. */
export function rekeyEntry(entry: QueuedWrite, oldId: string, newId: string): QueuedWrite {
  const swap = (text: string) => text.split(oldId).join(newId)
  const body = { ...entry.body }
  if (body.client_id === oldId) body.client_id = newId
  if (body.item_id === oldId) body.item_id = newId
  return { ...entry, clientId: swap(entry.clientId), path: swap(entry.path), body }
}
