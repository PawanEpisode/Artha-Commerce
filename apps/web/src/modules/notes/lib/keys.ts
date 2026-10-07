import type { AggregateParams } from './filter-schema'

/** One place for query keys so mutations invalidate exactly what they change. */
export const notesKeys = {
  all: ['notes'] as const,
  list: (params: object) => ['notes', 'list', params] as const,
  lists: ['notes', 'list'] as const,
  note: (id: string) => ['notes', 'note', id] as const,
  notes: ['notes', 'note'] as const,
  versions: (id: string) => ['notes', 'versions', id] as const,
  version: (id: string, rev: number) => ['notes', 'version', id, rev] as const,
  aggregate: (params: AggregateParams) => ['notes', 'aggregate', params] as const,
  aggregates: ['notes', 'aggregate'] as const,
  counts: (subject: string) => ['notes', 'counts', subject] as const,
  allCounts: ['notes', 'counts'] as const,
  overview: (level: string, subject: string, chapter: string) =>
    ['notes', 'overview', level, subject, chapter] as const,
  overviews: ['notes', 'overview'] as const,
  search: (params: object) => ['notes', 'search', params] as const,
  tags: ['notes', 'tags'] as const,
  suggest: (noteId: string) => ['notes', 'suggest', noteId] as const,
  settings: ['notes', 'settings'] as const,
  usage: ['notes', 'usage'] as const,
  trash: ['notes', 'trash'] as const,
  queue: ['notes', 'offline-queue'] as const,
  documents: (params: object) => ['notes', 'documents', params] as const,
  documentLists: ['notes', 'documents'] as const,
  document: (id: string) => ['notes', 'document', id] as const,
  documentProcessing: (id: string) => ['notes', 'document', id, 'processing'] as const,
  /** Text of a 20-page chunk (`chunk` = floor((page - 1) / 20)). */
  pageText: (id: string, chunk: number) => ['notes', 'document', id, 'text', chunk] as const,
  documentSearch: (id: string, q: string) => ['notes', 'document', id, 'search', q] as const,
  exportJob: (id: string) => ['notes', 'export', id] as const,
  parked: ['notes', 'parked'] as const,
}
