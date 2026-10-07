import { z } from 'zod'

import type { DocumentListParams, DocumentStatus, SourceKind } from './document-types'

/** The statuses the library can be narrowed to (the API's own names; "preparing" is `scanning`). */
export const LIBRARY_STATUSES = ['ready', 'scanning', 'needs_password', 'rejected', 'failed', 'expired'] as const
export const SOURCE_KINDS = ['institute_material', 'coaching', 'own_notes', 'handwritten', 'other'] as const

export const STATUS_LABEL: Record<(typeof LIBRARY_STATUSES)[number], string> = {
  ready: 'Ready',
  scanning: 'Preparing',
  needs_password: 'Locked',
  rejected: 'Rejected',
  failed: 'Failed',
  expired: 'Upload expired',
}

export const SOURCE_LABEL: Record<SourceKind, string> = {
  institute_material: 'Institute material',
  coaching: 'Coaching',
  own_notes: 'My own notes',
  handwritten: 'Handwritten',
  other: 'Other',
}

/**
 * `/app/notes/library?subject=&chapter=&status=&tag=&q=&sort=&source=`. Every value is optional and a bad one is dropped
 * (never an error), so a stale or hand-edited link still opens the library.
 */
export const librarySearchSchema = z.object({
  subject: z.string().max(120).optional().catch(undefined),
  chapter: z.string().max(120).optional().catch(undefined),
  status: z.enum(LIBRARY_STATUSES).optional().catch(undefined),
  tag: z.uuid().optional().catch(undefined),
  source: z.enum(SOURCE_KINDS).optional().catch(undefined),
  q: z.string().trim().max(200).optional().catch(undefined),
  sort: z.enum(['recent', 'title']).optional().catch(undefined),
})
export type LibrarySearch = z.infer<typeof librarySearchSchema>

export type LibraryFilterKey = 'subject' | 'chapter' | 'status' | 'tag' | 'source' | 'q'

/** Filters that are on (the sort is not a filter). A chapter without its subject is dropped, it means nothing alone. */
export function activeLibraryFilters(search: LibrarySearch): LibraryFilterKey[] {
  const keys: LibraryFilterKey[] = ['subject', 'chapter', 'status', 'tag', 'source', 'q']
  return keys.filter((key) => search[key] !== undefined && search[key] !== '')
}

export function withoutLibraryFilter(search: LibrarySearch, key: LibraryFilterKey): LibrarySearch {
  const { [key]: _removed, ...rest } = search
  if (key !== 'subject') return rest
  const { chapter: _chapter, ...others } = rest as LibrarySearch
  return others
}

/** What `GET documents/` is asked. The subject key needs the level of the enrolment. */
export function libraryListParams(search: LibrarySearch, level: string | undefined, limit = 24): DocumentListParams {
  return {
    subject: search.subject,
    level: search.subject || search.chapter ? level : undefined,
    chapter: search.subject ? search.chapter : undefined,
    tag: search.tag,
    status: search.status as DocumentStatus | undefined,
    source: search.source,
    q: search.q,
    sort: search.sort ?? 'recent',
    limit,
  }
}
