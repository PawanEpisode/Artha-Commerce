import type { NoteFilterSearch } from './filter-schema'
import type { Note, NoteSummary } from './types'

export interface LocalFilter {
  subject?: string
  chapter?: string
  topic?: string
  unfiled?: boolean
  pinned?: boolean
  q?: string
  search?: Pick<NoteFilterSearch, 'tag' | 'from' | 'to'>
}

const day = (iso: string) => iso.slice(0, 10)

/**
 * The same filters the server applies, for the offline copies (FR-F03-63): by subject, chapter and topic key, unfiled,
 * pinned, tag, date range and a plain text match. Trashed notes never show. Newest first.
 */
export function filterCached<T extends NoteSummary>(notes: readonly T[], filter: LocalFilter): T[] {
  const q = filter.q?.trim().toLowerCase()
  return notes
    .filter((n) => n.deleted_at === null)
    .filter((n) => (filter.subject ? n.link.subject_key === filter.subject : true))
    .filter((n) => (filter.chapter ? n.link.chapter_key === filter.chapter : true))
    .filter((n) => (filter.topic ? n.link.topic_key === filter.topic : true))
    .filter((n) => (filter.unfiled ? n.link.chapter_id === null && n.link.chapter_key === null : true))
    .filter((n) => (filter.pinned ? n.pinned : true))
    .filter((n) => (filter.search?.tag ? n.tags.some((t) => t.id === filter.search?.tag) : true))
    .filter((n) => (filter.search?.from ? day(n.updated_at) >= filter.search.from : true))
    .filter((n) => (filter.search?.to ? day(n.updated_at) <= filter.search.to : true))
    .filter((n) => (q ? `${n.title} ${n.snippet}`.toLowerCase().includes(q) : true))
    .sort((a, b) => (a.updated_at < b.updated_at ? 1 : a.updated_at > b.updated_at ? -1 : a.id < b.id ? 1 : -1))
}

/** A full note reduced to what lists show. */
export function toSummary(note: Note): NoteSummary {
  const { client_id: _c, body_md: _b, lang: _l, clip_source: _s, image_ids: _i, ...summary } = note
  return summary
}
