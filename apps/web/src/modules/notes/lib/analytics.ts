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

  itemLinked: (via: 'manual' | 'suggestion' | 'document_default' | 'clip' | 'capture') =>
    track('item_linked_to_chapter', { via }),

  aggregateViewed: (p: { tab: string; filters: number; items: number }) =>
    track('aggregate_viewed', { tab: p.tab, filters_count: p.filters, items_bucket: countBucket(p.items) }),
  chapterNotesSeen: (p: { tab: string; filters: number; items: number }) =>
    track('chapter_notes_seen', { tab: p.tab, filters_count: p.filters, items_bucket: countBucket(p.items) }),

  searchPerformed: (p: { scope: string; queryLength: string; results: string }) =>
    track('notes_search_performed', { scope: p.scope, query_length_bucket: p.queryLength, result_bucket: p.results }),
  searchResultOpened: (p: { scope: string; queryLength: string; results: string }) =>
    track('search_result_opened', { scope: p.scope, query_length_bucket: p.queryLength, result_bucket: p.results }),

  quotaBlocked: (kind: 'storage' | 'notes' | 'tags') => track('notes_quota_blocked', { kind }),

  exportRequested: () => track('export_requested', { options: 'all_notes' }),
  settingsChanged: (changedKeys: string[]) => track('notes_settings_changed', { changed_keys: changedKeys }),
}
