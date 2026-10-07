import { ageBucket, track } from '~/modules/observability'

import { type CountBucket, countBucket, notesAnalytics } from './analytics'
import type { ColorKey, MarkKind, Resolution } from './annotation-types'

/**
 * Product events of the annotation layer and the reader (PRD 10.1). Buckets and the fixed vocabulary below only: never a
 * quote, a comment, a title, a file name, a chapter name or the id of a mark or document.
 */

export type AddTool = 'selection' | 'area' | 'pen' | 'tap'
export type DeviceClass = 'touch' | 'pen' | 'desktop'
export type OpenedFrom = 'library' | 'search' | 'chapter' | 'aggregate'

export type DurationBucket = '<1m' | '1-5m' | '5-15m' | '15-60m' | '60m+'
export const durationBucket = (ms: number): DurationBucket =>
  ms < 60_000 ? '<1m' : ms < 300_000 ? '1-5m' : ms < 900_000 ? '5-15m' : ms < 3_600_000 ? '15-60m' : '60m+'

export type PagesViewedBucket = '1' | '2-5' | '6-20' | '21-100' | '100+'
export const pagesViewedBucket = (n: number): PagesViewedBucket =>
  n <= 1 ? '1' : n <= 5 ? '2-5' : n <= 20 ? '6-20' : n <= 100 ? '21-100' : '100+'

/** `pen` once a stylus was seen, otherwise `touch` on a coarse pointer, otherwise `desktop`. */
let sawPen = false
export const noteDeviceInput = (pointerType: string) => {
  if (pointerType === 'pen') sawPen = true
}
export function deviceClass(): DeviceClass {
  if (sawPen) return 'pen'
  const coarse = typeof window !== 'undefined' && window.matchMedia?.('(pointer: coarse)').matches
  return coarse ? 'touch' : 'desktop'
}

const FIRST_KEY = 'notes.annotation.first'
/** True once, for the first mark this browser ever makes (best effort; blocked storage reads as "not first" again). */
export function isFirstMark(): boolean {
  try {
    if (window.localStorage.getItem(FIRST_KEY)) return false
    window.localStorage.setItem(FIRST_KEY, '1')
    return true
  } catch {
    return false
  }
}

export const annotationAnalytics = {
  added: (p: { kind: MarkKind; color: ColorKey | null; hasChapter: boolean; tool: AddTool }) =>
    track('annotation_added', {
      kind: p.kind,
      color_key: p.color ?? 'none',
      has_chapter: p.hasChapter,
      tool: p.tool,
      device_class: deviceClass(),
      first: isFirstMark(),
    }),
  edited: (kind: MarkKind) => track('annotation_edited', { kind }),
  deleted: (kind: MarkKind) => track('annotation_deleted', { kind }),
  undone: (kind: MarkKind) => track('annotation_undone', { kind }),
  conflictResolved: (choice: Resolution, kind: MarkKind) => track('annotation_conflict_resolved', { choice, kind }),

  writeQueued: (count: number) => track('notes_write_queued', { count: countBucket(count), kind: 'annotation' }),
  queueReplayed: (count: number, oldestQueuedAt?: number) =>
    track('notes_queue_replayed', {
      count: countBucket(count),
      age_bucket: oldestQueuedAt ? ageBucket(Math.max(0, Date.now() - oldestQueuedAt)) : undefined,
      kind: 'annotation',
    }),

  linked: (via: 'manual' | 'range' | 'document_default') => notesAnalytics.itemLinked(via),
  cardCreated: (p: { kind: MarkKind; existing: boolean; oneTap: boolean }) =>
    track('recall_card_created_from_note', {
      source_type: 'annotation',
      kind: p.kind,
      one_tap: p.oneTap,
      existing: p.existing,
    }),
  readingSessionEnded: (p: { durationMs: number; pagesViewed: number; marksAdded: number }) =>
    track('pdf_reading_session_ended', {
      duration_bucket: durationBucket(p.durationMs),
      pages_viewed_bucket: pagesViewedBucket(p.pagesViewed),
      marks_added: countBucket(p.marksAdded) satisfies CountBucket,
    }),
  chapterMarksSeen: (p: { filters: number; items: number }) => notesAnalytics.chapterNotesSeen({ tab: 'reader', ...p }),
}
