import { describe, expect, it } from 'vitest'

import { activeLibraryFilters, libraryListParams, librarySearchSchema, withoutLibraryFilter } from './library-schema'

const TAG = '3f1f3a1e-1c1d-4c8e-9a4b-0a1b2c3d4e5f'

describe('library URL schema', () => {
  it('accepts a full valid URL', () => {
    expect(
      librarySearchSchema.parse({
        subject: 'tax',
        chapter: 'itc',
        status: 'ready',
        tag: TAG,
        q: ' gst ',
        sort: 'title',
      }),
    ).toEqual({
      subject: 'tax',
      chapter: 'itc',
      status: 'ready',
      tag: TAG,
      q: 'gst',
      sort: 'title',
    })
  })
  it('drops a bad value instead of failing, and keeps the rest', () => {
    const parsed = librarySearchSchema.parse({ status: 'weird', tag: 'not-a-uuid', sort: 'size', subject: 'tax' })
    expect(parsed).toEqual({ subject: 'tax' })
  })
  it('counts filters but not the sort, and dropping a subject drops its chapter', () => {
    const search = { subject: 'tax', chapter: 'itc', sort: 'title' as const, q: 'gst' }
    expect(activeLibraryFilters(search)).toEqual(['subject', 'chapter', 'q'])
    expect(withoutLibraryFilter(search, 'subject')).toEqual({ sort: 'title', q: 'gst' })
    expect(withoutLibraryFilter(search, 'q')).toEqual({ subject: 'tax', chapter: 'itc', sort: 'title' })
  })
  it('asks the API with the level only when a subject needs it, newest first by default', () => {
    expect(libraryListParams({}, 'L1')).toMatchObject({ level: undefined, sort: 'recent', limit: 24 })
    expect(libraryListParams({ subject: 'tax', chapter: 'itc' }, 'L1')).toMatchObject({
      level: 'L1',
      subject: 'tax',
      chapter: 'itc',
    })
    expect(libraryListParams({ chapter: 'itc' }, 'L1').chapter).toBeUndefined()
  })
})
