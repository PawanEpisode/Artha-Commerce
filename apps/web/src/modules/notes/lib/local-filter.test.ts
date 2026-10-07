import { describe, expect, it } from 'vitest'

import { filterCached, toSummary } from './local-filter'
import { FILED_LINK, makeNote } from './testing'

const TAG = '3f2b8c1e-5a4d-4e9b-8c7a-1d2e3f4a5b6c'
const notes = [
  makeNote({
    id: 'a',
    title: 'Blocked credits',
    updated_at: '2026-10-03T10:00:00Z',
    link: FILED_LINK,
    tags: [{ id: TAG, name: 'doubt', color_key: null }],
  }),
  makeNote({ id: 'b', title: 'Place of supply', snippet: 'Rules for services', updated_at: '2026-10-05T10:00:00Z' }),
  makeNote({
    id: 'c',
    title: 'Old',
    updated_at: '2026-09-01T10:00:00Z',
    pinned: true,
    link: { ...FILED_LINK, chapter_key: 'other', chapter_id: 'c2' },
  }),
  makeNote({ id: 'd', title: 'In trash', deleted_at: '2026-10-06T10:00:00Z' }),
]
const ids = (list: ReturnType<typeof filterCached>) => list.map((n) => n.id)

describe('filterCached', () => {
  it('returns live notes newest first and never shows the trash', () => {
    expect(ids(filterCached(notes, {}))).toEqual(['b', 'a', 'c'])
  })

  it('filters by subject, chapter and unfiled', () => {
    expect(ids(filterCached(notes, { subject: 'taxation' }))).toEqual(['a', 'c'])
    expect(ids(filterCached(notes, { subject: 'taxation', chapter: 'gst-itc' }))).toEqual(['a'])
    expect(ids(filterCached(notes, { unfiled: true }))).toEqual(['b'])
  })

  it('filters by tag, date range, pinned and a text match on title and snippet', () => {
    expect(ids(filterCached(notes, { search: { tag: TAG } }))).toEqual(['a'])
    expect(ids(filterCached(notes, { search: { from: '2026-10-01', to: '2026-10-04' } }))).toEqual(['a'])
    expect(ids(filterCached(notes, { pinned: true }))).toEqual(['c'])
    expect(ids(filterCached(notes, { q: 'SERVICES' }))).toEqual(['b'])
  })
})

describe('toSummary', () => {
  it('drops the body and the fields only a full note has', () => {
    const summary = toSummary(makeNote())
    expect(summary).not.toHaveProperty('body_md')
    expect(summary).not.toHaveProperty('client_id')
    expect(summary.title).toBe('Blocked credits')
  })
})
