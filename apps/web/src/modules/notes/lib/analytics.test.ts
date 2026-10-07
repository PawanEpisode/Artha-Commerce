import { beforeEach, describe, expect, it, vi } from 'vitest'

const track = vi.fn()
vi.mock('~/modules/observability', async () => ({
  track: (...args: unknown[]) => track(...args),
  ageBucket: (ms: number) => (ms < 3_600_000 ? '<1h' : ms < 86_400_000 ? '<1d' : ms < 7 * 86_400_000 ? '<7d' : '7d+'),
}))

const { charsBucket, countBucket, notesAnalytics } = await import('./analytics')

beforeEach(() => track.mockClear())

describe('buckets', () => {
  it('reports counts and sizes as ranges', () => {
    expect([0, 3, 12, 99].map(countBucket)).toEqual(['0', '1-5', '6-20', '21+'])
    expect([0, 10, 800, 5000, 20000].map(charsBucket)).toEqual(['0', '1-500', '501-2000', '2001-10000', '10001+'])
  })
})

describe('events carry no text', () => {
  it('sends only ranges, flags and the fixed vocabulary', () => {
    notesAnalytics.hubViewed({ unfiled: 7, notes: 40 })
    notesAnalytics.noteCreated({ source: 'capture', hasChapter: true, first: true })
    notesAnalytics.noteSaved({ autosave: true, chars: 1234, offline: false })
    notesAnalytics.searchPerformed({ scope: 'notes', queryLength: '4-10', results: '1-5' })
    notesAnalytics.conflictResolved('both')
    notesAnalytics.settingsChanged(['colour'])
    const sent = track.mock.calls
    expect(sent.map(([event]) => event)).toEqual([
      'notes_hub_viewed',
      'note_created',
      'note_saved',
      'notes_search_performed',
      'note_conflict_resolved',
      'notes_settings_changed',
    ])
    for (const [, props] of sent) {
      for (const value of Object.values(props as Record<string, unknown>)) {
        // Booleans, short vocabulary words and ranges only: never free text, ids or numbers that could identify a note.
        expect(
          typeof value === 'boolean' || (typeof value === 'string' && value.length <= 12) || Array.isArray(value),
        ).toBe(true)
      }
    }
    expect(track.mock.calls[2]![1]).toEqual({
      autosave: true,
      chars_bucket: '501-2000',
      offline: false,
    })
  })

  it('reports the age of a deleted note in a bucket, never the date or the id', () => {
    notesAnalytics.noteDeleted(new Date(Date.now() - 2 * 86_400_000).toISOString())
    expect(track).toHaveBeenCalledWith('note_deleted', { kind: 'note', age_bucket: '<7d' })
  })
})

describe('R2 events (PRD 10.1) carry buckets only', () => {
  it('buckets sizes, pages and durations', async () => {
    const { bytesBucket, durationBucket, pagesBucket } = await import('./analytics')
    expect([1, 6 * 1024 * 1024, 30 * 1024 * 1024, 60 * 1024 * 1024].map(bytesBucket)).toEqual([
      '<5MB',
      '5-25MB',
      '25-50MB',
      '50MB+',
    ])
    expect([null, 0, 10, 100, 300, 900].map(pagesBucket)).toEqual([
      'unknown',
      'unknown',
      '1-50',
      '51-200',
      '201-500',
      '501+',
    ])
    expect([5_000, 30_000, 120_000, 600_000].map(durationBucket)).toEqual(['<10s', '10-60s', '1-5m', '5m+'])
  })

  it('never sends a name, title, query or id', () => {
    notesAnalytics.pdfUploadStarted({ bytes: 3_000_000, pages: 120 })
    notesAnalytics.pdfUploadCompleted({
      bytes: 3_000_000,
      pages: 120,
      durationMs: 20_000,
      encrypted: false,
      scanned: true,
    })
    notesAnalytics.pdfUploadFailed({ bytes: 3_000_000, pages: null, reason: 'network' })
    notesAnalytics.ocrRequested({ pages: 320, lang: 'eng' })
    notesAnalytics.ocrCompleted({ pages: 320, durationMs: 90_000 })
    notesAnalytics.ocrFailed({ pages: 320 })
    notesAnalytics.exportRequested({ options: 'marks_appendix' })
    notesAnalytics.quotaBlocked('ocr')
    notesAnalytics.searchPerformed({ scope: 'pdf', queryLength: '4-10', results: '1-5' })
    notesAnalytics.searchResultOpened({ scope: 'pdf', queryLength: '4-10', results: '1-5' })
    notesAnalytics.aggregateViewed({ tab: 'highlights', filters: 1, items: 12 })
    const sent = track.mock.calls
    expect(sent.map(([event]) => event)).toEqual([
      'pdf_upload_started',
      'pdf_upload_completed',
      'pdf_upload_failed',
      'ocr_requested',
      'ocr_completed',
      'ocr_failed',
      'export_requested',
      'notes_quota_blocked',
      'notes_search_performed',
      'search_result_opened',
      'aggregate_viewed',
    ])
    const text = JSON.stringify(sent)
    expect(text).not.toMatch(/\.pdf|title|filename|document_id|"q"/i)
    expect(sent[7]?.[1]).toEqual({ kind: 'ocr' })
    expect(sent[8]?.[1]).toMatchObject({ scope: 'pdf' })
  })
})
