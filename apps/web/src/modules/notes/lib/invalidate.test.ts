import { QueryClient } from '@tanstack/react-query'
import { describe, expect, it, vi } from 'vitest'

import { invalidateAfterNoteLink } from './invalidate'
import { notesKeys } from './keys'

describe('invalidateAfterNoteLink', () => {
  it('refetches only the subjects that lost or gained the note', async () => {
    const qc = new QueryClient()
    const spy = vi.spyOn(qc, 'invalidateQueries').mockResolvedValue(undefined)
    await invalidateAfterNoteLink(qc, [null, 'taxation'])
    const keys = spy.mock.calls.map((call) => call[0]?.queryKey)
    expect(keys).toEqual(
      expect.arrayContaining([
        notesKeys.lists,
        notesKeys.aggregates,
        notesKeys.overviews,
        notesKeys.counts('taxation'),
      ]),
    )
    expect(keys).not.toContainEqual(notesKeys.allCounts)
    expect(keys).not.toContainEqual(notesKeys.usage)
    expect(keys).not.toContainEqual(notesKeys.tags)
  })

  it('falls back to every subject count when neither side has a subject key', async () => {
    const qc = new QueryClient()
    const spy = vi.spyOn(qc, 'invalidateQueries').mockResolvedValue(undefined)
    await invalidateAfterNoteLink(qc, [null, undefined])
    expect(spy.mock.calls.map((call) => call[0]?.queryKey)).toContainEqual(notesKeys.allCounts)
  })
})
