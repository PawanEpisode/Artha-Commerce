import { createKvDatabase } from '~/lib/kv-store'

import type { LinkSelection } from './chapter-link'
import type { Note } from './types'

/**
 * Per-device copies for offline use: the last 200 notes the student opened (FR-F03-63) and the drafts of text that has
 * not reached the server yet. Everything is keyed by user so a shared device never mixes two students.
 */

/** How many opened notes stay readable offline. */
export const RECENT_LIMIT = 200

const db = createKvDatabase('artha-notes', 1, ['notes', 'drafts'])
const notes = db.store<CachedNote>('notes')
const drafts = db.store<Draft>('drafts')

export interface CachedNote {
  userId: string
  note: Note
  lastOpenedAt: number
  /** Text written offline that the server has not confirmed yet. */
  pending: boolean
}

export interface Draft {
  userId: string
  /** `note:<id>` for an existing note, `new:<clientId>` for one that was never saved. */
  key: string
  noteId: string | null
  clientId: string
  title: string
  body: string
  /** What the server had when the text was loaded, so a stale draft can be recognised. */
  baseRev: number | null
  /** The text at `baseRev`, sent as `base_body_md` so the server can merge a stale save. */
  baseBody?: string
  /** Where an unsaved new note was going to be filed. */
  selection?: LinkSelection | null
  updatedAt: number
}

const cacheKey = (userId: string, noteId: string) => `${userId}:${noteId}`
export const draftKey = (noteId: string | null, clientId: string) => (noteId ? `note:${noteId}` : `new:${clientId}`)

/** The entries to drop so at most `limit` remain: the least recently opened go first. Pure, for tests. */
export function pickEvictions(entries: readonly Pick<CachedNote, 'lastOpenedAt'>[], limit: number): number[] {
  return entries
    .map((entry, index) => ({ index, at: entry.lastOpenedAt }))
    .sort((a, b) => b.at - a.at)
    .slice(limit)
    .map((e) => e.index)
}

export async function cacheNote(userId: string, note: Note, options: { pending?: boolean; now?: number } = {}) {
  await notes.put(cacheKey(userId, note.id), {
    userId,
    note: { ...note, offline_copy: undefined },
    lastOpenedAt: options.now ?? Date.now(),
    pending: options.pending ?? false,
  })
  const mine = (await notes.all()).filter((e) => e.userId === userId)
  for (const index of pickEvictions(mine, RECENT_LIMIT)) {
    const evicted = mine[index]
    if (evicted) await notes.remove(cacheKey(userId, evicted.note.id))
  }
}

export async function readCachedNote(userId: string, noteId: string): Promise<CachedNote | undefined> {
  const found = await notes.get(cacheKey(userId, noteId))
  return found?.userId === userId ? found : undefined
}

/** Every cached note of the user, marked as an offline copy. Trashed ones are left to the filter. */
export async function cachedNotes(userId: string): Promise<Note[]> {
  return (await notes.all()).filter((e) => e.userId === userId).map((e) => ({ ...e.note, offline_copy: true }))
}

export const removeCachedNote = (userId: string, noteId: string) => notes.remove(cacheKey(userId, noteId))

export const saveDraft = (draft: Draft) => drafts.put(`${draft.userId}:${draft.key}`, draft)
export const clearDraft = (userId: string, key: string) => drafts.remove(`${userId}:${key}`)
export async function loadDraft(userId: string, key: string): Promise<Draft | undefined> {
  const found = await drafts.get(`${userId}:${key}`)
  return found?.userId === userId ? found : undefined
}

/** Drafts of notes that were never saved, newest first ("Recovered draft" on /app/notes/new). */
export async function unsavedNewDrafts(userId: string): Promise<Draft[]> {
  return (await drafts.all())
    .filter((d) => d.userId === userId && d.noteId === null && (d.body.trim() !== '' || d.title.trim() !== ''))
    .sort((a, b) => b.updatedAt - a.updatedAt)
}

/** Forget everything kept for this user (account deletion, "Delete all my notes"). */
export async function clearUserData(userId: string) {
  for (const entry of await notes.all())
    if (entry.userId === userId) await notes.remove(cacheKey(userId, entry.note.id))
  for (const draft of await drafts.all()) if (draft.userId === userId) await drafts.remove(`${userId}:${draft.key}`)
}

export const resetOfflineStore = () => db.reset()
