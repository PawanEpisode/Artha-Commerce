import { ageBucket, track } from '~/modules/observability'

/**
 * Product events of Smart Notes R1 (PRD 10.1). Names are `noun_verb`. No note text, title, tag name, chapter name,
 * search query or note id is ever sent: only counts and ranges, and the fixed vocabulary below.
 */

export type CountBucket = '0' | '1-5' | '6-20' | '21+'
export const countBucket = (n: number): CountBucket => (n <= 0 ? '0' : n <= 5 ? '1-5' : n <= 20 ? '6-20' : '21+')

export type CharsBucket = '0' | '1-500' | '501-2000' | '2001-10000' | '10001+'
export const charsBucket = (n: number): CharsBucket =>
  n <= 0 ? '0' : n <= 500 ? '1-500' : n <= 2000 ? '501-2000' : n <= 10_000 ? '2001-10000' : '10001+'

export type BytesBucket = '<5MB' | '5-25MB' | '25-50MB' | '50MB+'
export const bytesBucket = (n: number): BytesBucket =>
  n < 5 * 1024 * 1024 ? '<5MB' : n < 25 * 1024 * 1024 ? '5-25MB' : n < 50 * 1024 * 1024 ? '25-50MB' : '50MB+'

export type PagesBucket = 'unknown' | '1-50' | '51-200' | '201-500' | '501+'
export const pagesBucket = (n: number | null | undefined): PagesBucket =>
  !n || n <= 0 ? 'unknown' : n <= 50 ? '1-50' : n <= 200 ? '51-200' : n <= 500 ? '201-500' : '501+'

export type DurationBucket = '<10s' | '10-60s' | '1-5m' | '5m+'
export const durationBucket = (ms: number): DurationBucket =>
  ms < 10_000 ? '<10s' : ms < 60_000 ? '10-60s' : ms < 300_000 ? '1-5m' : '5m+'

export type UploadFailReason =
  'network' | 'too_large' | 'too_many_pages' | 'type' | 'scan_rejected' | 'quota' | 'server'
export type QuotaKind = 'storage' | 'documents' | 'notes' | 'tags' | 'ocr' | 'export'

const age = (iso: string | null | undefined, now = Date.now()) =>
  iso ? ageBucket(Math.max(0, now - new Date(iso).getTime())) : undefined

export const notesAnalytics = {
  hubViewed: (counts: { unfiled: number; notes: number; docs?: number }) =>
    track('notes_hub_viewed', {
      unfiled_bucket: countBucket(counts.unfiled),
      notes_bucket: countBucket(counts.notes),
      docs_bucket: countBucket(counts.docs ?? 0),
    }),

  noteCreated: (p: { source: 'new' | 'capture' | 'clip' | 'summary'; hasChapter: boolean; first: boolean }) =>
    track('note_created', { source: p.source, has_chapter: p.hasChapter, kind: 'note', first: p.first }),

  noteSaved: (p: { autosave: boolean; chars: number; offline: boolean }) =>
    track('note_saved', { autosave: p.autosave, chars_bucket: charsBucket(p.chars), offline: p.offline }),

  noteDeleted: (createdAt: string) => track('note_deleted', { kind: 'note', age_bucket: age(createdAt) }),
  noteRestored: (createdAt: string) => track('note_restored', { kind: 'note', age_bucket: age(createdAt) }),
  versionRestored: (createdAt: string) => track('note_version_restored', { kind: 'note', age_bucket: age(createdAt) }),

  conflictResolved: (choice: 'mine' | 'theirs' | 'both') => track('note_conflict_resolved', { choice, kind: 'note' }),

  writeQueued: (count: number) => track('notes_write_queued', { count: countBucket(count), kind: 'note' }),
  queueReplayed: (count: number, oldestQueuedAt?: number) =>
    track('notes_queue_replayed', {
      count: countBucket(count),
      age_bucket: oldestQueuedAt ? ageBucket(Math.max(0, Date.now() - oldestQueuedAt)) : undefined,
      kind: 'note',
    }),

  itemLinked: (via: 'manual' | 'range' | 'suggestion' | 'document_default' | 'clip' | 'capture') =>
    track('item_linked_to_chapter', { via }),

  aggregateViewed: (p: { tab: string; filters: number; items: number }) =>
    track('aggregate_viewed', { tab: p.tab, filters_count: p.filters, items_bucket: countBucket(p.items) }),
  chapterNotesSeen: (p: { tab: string; filters: number; items: number }) =>
    track('chapter_notes_seen', { tab: p.tab, filters_count: p.filters, items_bucket: countBucket(p.items) }),

  searchPerformed: (p: { scope: string; queryLength: string; results: string }) =>
    track('notes_search_performed', { scope: p.scope, query_length_bucket: p.queryLength, result_bucket: p.results }),
  searchResultOpened: (p: { scope: string; queryLength: string; results: string }) =>
    track('search_result_opened', { scope: p.scope, query_length_bucket: p.queryLength, result_bucket: p.results }),

  quotaBlocked: (kind: QuotaKind) => track('notes_quota_blocked', { kind }),

  // R2 (PRD 10.1): buckets and the fixed vocabulary only, never a file name, title, query or id.
  pdfUploadStarted: (p: { bytes: number; pages: number | null }) =>
    track('pdf_upload_started', { bytes_bucket: bytesBucket(p.bytes), pages_bucket: pagesBucket(p.pages) }),
  pdfUploadCompleted: (p: {
    bytes: number
    pages: number | null
    durationMs: number
    encrypted: boolean
    scanned: boolean
  }) =>
    track('pdf_upload_completed', {
      bytes_bucket: bytesBucket(p.bytes),
      pages_bucket: pagesBucket(p.pages),
      duration_bucket: durationBucket(p.durationMs),
      encrypted: p.encrypted,
      scanned: p.scanned,
    }),
  pdfUploadFailed: (p: { bytes: number; pages: number | null; reason: UploadFailReason }) =>
    track('pdf_upload_failed', {
      bytes_bucket: bytesBucket(p.bytes),
      pages_bucket: pagesBucket(p.pages),
      reason: p.reason,
    }),
  ocrRequested: (p: { pages: number; lang: string }) =>
    track('ocr_requested', { mode: 'tesseract', lang: p.lang, pages_bucket: pagesBucket(p.pages) }),
  ocrCompleted: (p: { pages: number; durationMs?: number }) =>
    track('ocr_completed', {
      mode: 'tesseract',
      pages_bucket: pagesBucket(p.pages),
      ...(p.durationMs !== undefined ? { duration_bucket: durationBucket(p.durationMs) } : {}),
    }),
  ocrFailed: (p: { pages: number }) => track('ocr_failed', { mode: 'tesseract', pages_bucket: pagesBucket(p.pages) }),

  exportRequested: (p?: { pages?: number | null; options?: 'all_notes' | 'marks' | 'marks_appendix' | 'archive' }) =>
    track('export_requested', {
      options: p?.options ?? 'all_notes',
      ...(p && 'pages' in p ? { pages_bucket: pagesBucket(p.pages) } : {}),
    }),
  exportCompleted: (p: { pages?: number | null; options: 'marks' | 'marks_appendix' | 'archive' }) =>
    track('export_completed', { options: p.options, pages_bucket: pagesBucket(p.pages) }),
  settingsChanged: (changedKeys: string[]) => track('notes_settings_changed', { changed_keys: changedKeys }),
}
