import { z } from 'zod'

/** The note views a student can switch between. Highlights and PDFs arrive with release R2; the URL accepts them now. */
export const NOTE_TABS = ['all', 'notes', 'highlights', 'documents'] as const
export type NoteTab = (typeof NOTE_TABS)[number]

const ISO_DAY = /^\d{4}-\d{2}-\d{2}$/

const day = z
  .string()
  .regex(ISO_DAY)
  .refine((s) => !Number.isNaN(Date.parse(`${s}T00:00:00Z`)))
  .optional()
  .catch(undefined)

/**
 * Filters of the subject and chapter views, all in the URL so a view can be shared, bookmarked and restored. A bad
 * value never breaks the page: it is dropped (`.catch(undefined)`) and the rest still applies.
 */
export const noteFilterSchema = z.object({
  tab: z.enum(NOTE_TABS).optional().catch(undefined),
  tag: z.uuid().optional().catch(undefined),
  color: z.string().max(2).optional().catch(undefined),
  from: day,
  to: day,
  doc: z.uuid().optional().catch(undefined),
  sort: z.enum(['recent', 'page']).optional().catch(undefined),
  cursor: z.string().max(500).optional().catch(undefined),
  topic: z.string().max(120).optional().catch(undefined),
})
export type NoteFilterSearch = z.infer<typeof noteFilterSchema>

export const searchScopes = ['all', 'notes', 'highlights', 'pdf'] as const
export const noteSearchSchema = z.object({
  q: z.string().max(200).optional().catch(undefined),
  scope: z.enum(searchScopes).optional().catch(undefined),
  subject: z.string().max(120).optional().catch(undefined),
  chapter: z.string().max(120).optional().catch(undefined),
})
export type NoteSearchParams = z.infer<typeof noteSearchSchema>

/** `/app/notes/new?subject=&chapter=&topic=&level=`: prefills the link so a chapter page needs no picker. */
export const newNoteSchema = z.object({
  level: z.uuid().optional().catch(undefined),
  subject: z.string().max(120).optional().catch(undefined),
  chapter: z.string().max(120).optional().catch(undefined),
  topic: z.string().max(120).optional().catch(undefined),
})
export type NewNoteSearch = z.infer<typeof newNoteSchema>

/** The note editor's `?v=4` (open an old version) and `?panel=history`. */
export const noteEditorSchema = z.object({
  v: z.coerce.number().int().positive().optional().catch(undefined),
  panel: z.enum(['history']).optional().catch(undefined),
})
export type NoteEditorSearch = z.infer<typeof noteEditorSchema>

/** What the aggregate endpoint is asked. Built from the route (subject, chapter) and the URL filters. */
export interface AggregateParams {
  level: string
  subject?: string
  chapter?: string
  topic?: string
  tab: NoteTab
  tag?: string
  color?: string
  doc?: string
  from?: string
  to?: string
  unfiled?: boolean
  q?: string
  cursor?: string
}

/** The tab to use: the URL's, or "all". */
export const tabOf = (search: NoteFilterSearch): NoteTab => search.tab ?? 'all'

export function aggregateParams(
  base: { level: string; subject?: string; chapter?: string },
  search: NoteFilterSearch,
): AggregateParams {
  const ordered = search.from && search.to && search.from > search.to
  return {
    ...base,
    topic: search.topic,
    tab: tabOf(search),
    tag: search.tag,
    color: search.color,
    doc: search.doc,
    from: ordered ? search.to : search.from,
    to: ordered ? search.from : search.to,
    cursor: search.cursor,
  }
}

/** Query string for `GET aggregate/`: only what is set, in a stable order. */
export function aggregateQuery(params: AggregateParams, limit?: number): string {
  const query = new URLSearchParams()
  const add = (key: string, value: string | undefined) => value && query.set(key, value)
  add('level', params.level)
  add('subject', params.subject)
  add('chapter', params.chapter)
  add('topic', params.topic)
  add('tab', params.tab)
  add('tag', params.tag)
  add('color', params.color)
  add('doc', params.doc)
  add('from', params.from)
  add('to', params.to)
  add('q', params.q)
  if (params.unfiled) query.set('unfiled', '1')
  add('cursor', params.cursor)
  if (limit) query.set('limit', String(limit))
  return query.toString()
}

export type FilterKey = 'tag' | 'color' | 'from' | 'to' | 'doc' | 'topic'

/** Filters that are on, for the chips and the analytics count. The tab, sort and cursor are not filters. */
export function activeFilters(search: NoteFilterSearch): FilterKey[] {
  const keys: FilterKey[] = ['tag', 'color', 'from', 'to', 'doc', 'topic']
  return keys.filter((key) => search[key] !== undefined)
}

/** The URL after removing one filter. Also resets the cursor: a new filter starts at page one. */
export function withoutFilter(search: NoteFilterSearch, key: FilterKey): NoteFilterSearch {
  const { [key]: _removed, cursor: _cursor, ...rest } = search
  return rest
}

/** The strongest single filter to drop when nothing matches ("Try removing the tag"). Newest narrowing first. */
export function strongestFilter(search: NoteFilterSearch): FilterKey | null {
  const order: FilterKey[] = ['tag', 'color', 'doc', 'topic', 'from', 'to']
  return order.find((key) => search[key] !== undefined) ?? null
}
