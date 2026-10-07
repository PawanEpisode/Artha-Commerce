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
