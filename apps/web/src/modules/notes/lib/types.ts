/** Shapes returned by the notes API (`/api/v1/notes/...`). Mirrors docs/F-03-API-CONTRACT.md. */
import type { DocumentSummary } from './document-types'
import type { DocumentRow, HighlightRow } from './library-types'

export type NoteKind = 'note' | 'exam_summary'
export type NoteOrigin = 'typed' | 'clip' | 'ai_summary' | 'import'

/** Where a note is filed. Every key is null for an Unfiled note. Grouping is by (level, subject key, chapter key). */
export interface NoteLink {
  level_id: string | null
  subject_id: string | null
  subject_key: string | null
  subject_name: string | null
  chapter_id: string | null
  chapter_key: string | null
  chapter_name: string | null
  topic_id: string | null
  topic_key: string | null
  topic_name: string | null
  /** The chapter is no longer in the level's current syllabus scheme; the stored names are shown. */
  moved_or_removed: boolean
}

export interface TagRef {
  id: string
  name: string
  color_key: string | null
}

export interface Tag extends TagRef {
  /** Live items carrying the tag. */
  count: number
}

export interface NoteSummary {
  id: string
  kind: NoteKind
  origin: NoteOrigin
  title: string
  /** At most 200 characters of plain text. */
  snippet: string
  body_chars: number
  pinned: boolean
  is_current_summary: boolean
  link: NoteLink
  tags: TagRef[]
  rev: number
  created_at: string
  updated_at: string
  deleted_at: string | null
  purge_after: string | null
  /** Set by the offline cache, never by the server: this row is a copy kept on the device. */
  offline_copy?: boolean
  /**
   * Set by this device only: the note was created here and the server has not confirmed its row yet (the id is
   * client generated). Cleared when the create reaches the server.
   */
  local_only?: boolean
}

export interface ClipSource {
  module: string
  ref: string
  label: string
}

export interface Note extends NoteSummary {
  client_id: string | null
  body_md: string
  lang: string
  clip_source: ClipSource | null
  image_ids: string[]
}

export interface Page<T> {
  items: T[]
  next_cursor: string | null
}

/** Rows of `GET aggregate/`: notes, and from R2 marks and documents (`tab=highlights|documents|all`). */
export type AggregateItem = (NoteSummary & { type: 'note' }) | HighlightRow | DocumentRow

export interface ChapterCountsRow {
  chapter_id: string
  chapter_key: string
  name: string
  notes: number
  highlights: number
  marks: number
  documents: number
  has_summary: boolean
  last_noted_at: string | null
}

export interface MovedChapterRow {
  chapter_key: string
  chapter_name: string
  notes: number
  highlights: number
  marks: number
  documents: number
}

export interface SubjectCounts {
  subject_key: string
  chapters: ChapterCountsRow[]
  unfiled: number
  moved_or_removed: MovedChapterRow[]
}

export interface ChapterOverview {
  chapter: { id: string; key: string; name: string; subject_key: string; subject_name: string; level_id: string }
  counts: { notes: number; highlights: number; marks: number; documents: number }
  has_summary: boolean
  last_noted_at: string | null
  current_summary: NoteSummary | null
  recent: NoteSummary[]
  documents: DocumentSummary[]
}

export interface SearchHit {
  type: 'note'
  id: string
  title: string
  snippet: string
  link: NoteLink
  rank: number
  updated_at: string
}

export interface VersionRow {
  rev: number
  title: string
  source: 'autosave' | 'manual' | 'restore' | 'merge' | 'ai'
  chars: number
  created_at: string
}

export interface VersionDetail {
  rev: number
  title: string
  body_md: string
  source: VersionRow['source']
  created_at: string
}

export interface ChapterSuggestion {
  chapter_id: string
  chapter_key: string
  chapter_name: string
  subject_id: string
  subject_key: string
  subject_name: string
  score: number
}

export interface UsageLimits {
  max_storage_mb: number
  max_notes: number
  max_note_chars: number
  max_note_images: number
  max_tags: number
  [key: string]: number
}

export interface Usage {
  plan: string
  limits: UsageLimits
  used: { storage_bytes: number; notes: number; tags: number; [key: string]: number }
  resets_on: string
  /** R2: the five largest documents (trashed ones included) for the quota sheet. */
  largest_documents?: Array<{ id: string; title: string; bytes: number }>
}

/** What a 409 `note_conflict` carries: their version, what you sent, and a best-effort merge. */
export interface NoteConflictDetail {
  theirs: { rev: number; title: string; body_md: string; updated_at: string }
  mine: { title?: string; body_md?: string }
  merged: { body_md: string } | null
  device_label?: string
}

export type Resolution = 'mine' | 'theirs' | 'both'

/** The body of `PATCH notes/{id}/`. `base_rev` is required; everything else is optional. */
export interface NotePatch {
  base_rev: number
  title?: string
  body_md?: string
  base_body_md?: string
  chapter_id?: string | null
  topic_id?: string | null
  pinned?: boolean
  tag_ids?: string[]
  source?: 'autosave' | 'manual'
  resolution?: Resolution
  /** The scalar values you last saw, so the server can report which of them another device had changed. */
  base?: { title?: string; pinned?: boolean; chapter_id?: string | null; topic_id?: string | null }
}

export interface NoteCreate {
  client_id: string
  title?: string
  body_md?: string
  chapter_id?: string | null
  topic_id?: string | null
  tag_ids?: string[]
}

export interface PatchResult extends Note {
  merged?: boolean
  /** The note was in the Trash and this edit brought it back. */
  restored?: boolean
  /** Scalar fields where a newer value from another device was replaced by this edit (needs `base`). */
  overwritten?: string[]
}

export interface ChangesPage {
  items: Note[]
  next_since: string
  has_more: boolean
}
