import 'fake-indexeddb/auto'

import { beforeEach, describe, expect, it } from 'vitest'

import {
  clearAnnotationData,
  readCachedMarks,
  RECENT_DOCUMENTS,
  resetAnnotationStore,
  writeCachedMarks,
} from './annotation-store'
import { makeMark } from './annotation-testing'

const entry = (documentId: string, openedAt: number, userId = 'u1') => ({
  userId,
  documentId,
  marks: [
    makeMark({ id: `${documentId}-m`, document_id: documentId }),
    makeMark({ id: `${documentId}-gone`, document_id: documentId, deleted_at: '2026-10-01T00:00:00Z' }),
  ],
  sinceSeq: 7,
  syncedAt: 1,
  openedAt,
  marksInfo: { count: 1, limit: 20_000, near_limit: false },
})

beforeEach(() => resetAnnotationStore())

describe('the marks cache', () => {
  it('keeps marks with their tombstones and the change_seq the feed resumes from', async () => {
    await writeCachedMarks(entry('d1', 1))
    const cached = await readCachedMarks('u1', 'd1')
    expect(cached?.sinceSeq).toBe(7)
    expect(cached?.marks.map((m) => m.id)).toEqual(['d1-m', 'd1-gone'])
  })

  it('keeps the last three documents the student opened and drops the oldest', async () => {
    expect(RECENT_DOCUMENTS).toBe(3)
    for (const [i, id] of ['d1', 'd2', 'd3', 'd4'].entries()) await writeCachedMarks(entry(id, i + 1))
    expect(await readCachedMarks('u1', 'd1')).toBeUndefined()
    expect(await readCachedMarks('u1', 'd4')).toBeDefined()
    expect(await readCachedMarks('u1', 'd2')).toBeDefined()
  })

  it('never shows one user the marks of another, and forgets everything for a user on request', async () => {
    await writeCachedMarks(entry('d1', 1, 'u1'))
    await writeCachedMarks(entry('d1', 2, 'u2'))
    expect(await readCachedMarks('u2', 'd1')).toBeDefined()
    await clearAnnotationData('u1')
    expect(await readCachedMarks('u1', 'd1')).toBeUndefined()
    expect(await readCachedMarks('u2', 'd1')).toBeDefined()
  })
})
