import { charCount, plainText } from '~/lib/richtext'

import type { Note, NoteLink, TagRef } from './types'

/** What a student changed locally, in the shapes the screens show. */
export interface LocalEdit {
  title?: string
  body_md?: string
  pinned?: boolean
  link?: NoteLink
  tags?: TagRef[]
}

/**
 * The note as it should look right after a local edit, so a list, the offline copy and the editor agree before the
 * server confirms. `rev` is left alone: only the server moves it.
 */
export function applyLocalEdit(note: Note, edit: LocalEdit, now: string = new Date().toISOString()): Note {
  const next: Note = { ...note, updated_at: now }
  if (edit.title !== undefined) next.title = edit.title
  if (edit.body_md !== undefined) {
    next.body_md = edit.body_md
    next.snippet = plainText(edit.body_md).slice(0, 200)
    next.body_chars = charCount(edit.body_md)
  }
  if (edit.pinned !== undefined) next.pinned = edit.pinned
  if (edit.link !== undefined) next.link = edit.link
  if (edit.tags !== undefined) next.tags = edit.tags
  return next
}
