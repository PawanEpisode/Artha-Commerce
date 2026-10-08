import 'fake-indexeddb/auto'

import { beforeEach, describe, expect, it, vi } from 'vitest'

import { clearAllLocalData } from '~/lib/local-data'

import { readCachedMarks, resetAnnotationStore, writeCachedMarks } from './annotation-store'
import { clearNotesLocalData } from './local-data'
import { consumeOpenedFrom, markOpenedFrom } from './opened-from'

vi.mock('./queue', () => ({ queuedNoteWrites: async () => [] }))

const entry = (userId: string) => ({
  userId,
  documentId: 'd1',
  marks: [],
  sinceSeq: 1,
  syncedAt: 1,
  openedAt: 1,
  marksInfo: { count: 0, limit: 20_000, near_limit: false },
})

beforeEach(() => resetAnnotationStore())

describe('forgetting a student on this device', () => {
  it('removes the cached marks of that student only', async () => {
    await writeCachedMarks(entry('u1'))
    await writeCachedMarks(entry('u2'))
    await clearNotesLocalData('u1')
    expect(await readCachedMarks('u1', 'd1')).toBeUndefined()
    expect(await readCachedMarks('u2', 'd1')).toBeDefined()
  })

  it('runs as part of the shared account-deletion clearer', async () => {
    await writeCachedMarks(entry('u1'))
    expect(await clearAllLocalData('u1')).toEqual([])
    expect(await readCachedMarks('u1', 'd1')).toBeUndefined()
  })
})

describe('where a PDF was opened from', () => {
  it('is read once, then falls back to the link', () => {
    const store = new Map<string, string>()
    vi.stubGlobal('window', {
      sessionStorage: {
        getItem: (k: string) => store.get(k) ?? null,
        setItem: (k: string, v: string) => void store.set(k, v),
        removeItem: (k: string) => void store.delete(k),
      },
    })
    markOpenedFrom('chapter')
    expect(consumeOpenedFrom({})).toBe('chapter')
    expect(consumeOpenedFrom({ q: 'x' })).toBe('search')
    expect(consumeOpenedFrom({ ann: 'a' })).toBe('aggregate')
    expect(consumeOpenedFrom({})).toBe('library')
    vi.unstubAllGlobals()
  })
})
