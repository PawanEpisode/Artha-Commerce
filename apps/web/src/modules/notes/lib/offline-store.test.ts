import 'fake-indexeddb/auto'

import { beforeEach, describe, expect, it } from 'vitest'

import {
  cachedNotes,
  cacheNote,
  clearDraft,
  clearUserData,
  draftKey,
  loadDraft,
  pickEvictions,
  readCachedNote,
  RECENT_LIMIT,
  resetOfflineStore,
  saveDraft,
  unsavedNewDrafts,
} from './offline-store'
import { makeNote } from './testing'

beforeEach(async () => {
  resetOfflineStore()
  await clearUserData('u1')
  await clearUserData('u2')
})

describe('pickEvictions', () => {
  it('drops the least recently opened beyond the limit', () => {
    const entries = [{ lastOpenedAt: 5 }, { lastOpenedAt: 1 }, { lastOpenedAt: 9 }, { lastOpenedAt: 3 }]
    expect(pickEvictions(entries, 2).sort()).toEqual([1, 3])
    expect(pickEvictions(entries, 10)).toEqual([])
  })
})

describe('note cache', () => {
  it('keeps a note readable offline, marked as an offline copy, and never shows it to another user', async () => {
    await cacheNote('u1', makeNote({ id: 'n1' }))
    expect((await cachedNotes('u1')).map((n) => [n.id, n.offline_copy])).toEqual([['n1', true]])
    expect(await cachedNotes('u2')).toEqual([])
    expect(await readCachedNote('u2', 'n1')).toBeUndefined()
    expect((await readCachedNote('u1', 'n1'))?.note.body_md).toContain('ITC')
  })

  it('remembers that text is still waiting for the server', async () => {
    await cacheNote('u1', makeNote({ id: 'n1' }), { pending: true })
    expect((await readCachedNote('u1', 'n1'))?.pending).toBe(true)
  })

  it('keeps the 200 most recently opened notes', async () => {
    for (let i = 0; i < RECENT_LIMIT + 3; i++) await cacheNote('u1', makeNote({ id: `n${i}` }), { now: i })
    const kept = (await cachedNotes('u1')).map((n) => n.id)
    expect(kept).toHaveLength(RECENT_LIMIT)
    expect(kept).not.toContain('n0')
    expect(kept).toContain(`n${RECENT_LIMIT + 2}`)
  })
})

describe('drafts', () => {
  const draft = (over = {}) => ({
    userId: 'u1',
    key: draftKey(null, 'c1'),
    noteId: null,
    clientId: 'c1',
    title: '',
    body: 'half a thought',
    baseRev: null,
    updatedAt: 10,
    ...over,
  })

  it('saves a draft before anything reaches the server and restores it after a reload', async () => {
    await saveDraft(draft())
    resetOfflineStore()
    expect((await loadDraft('u1', 'new:c1'))?.body).toBe('half a thought')
    expect(await loadDraft('u2', 'new:c1')).toBeUndefined()
  })

  it('lists unsaved new-note drafts, newest first, and skips empty ones', async () => {
    await saveDraft(draft({ key: 'new:a', clientId: 'a', updatedAt: 1 }))
    await saveDraft(draft({ key: 'new:b', clientId: 'b', updatedAt: 2 }))
    await saveDraft(draft({ key: 'new:e', clientId: 'e', body: '  ' }))
    await saveDraft(draft({ key: 'note:n1', noteId: 'n1', clientId: 'x' }))
    expect((await unsavedNewDrafts('u1')).map((d) => d.clientId)).toEqual(['b', 'a'])
  })

  it('clears a draft once it is safe on the server', async () => {
    await saveDraft(draft())
    await clearDraft('u1', 'new:c1')
    expect(await loadDraft('u1', 'new:c1')).toBeUndefined()
  })

  it('names the draft of an existing note by its id', () => {
    expect(draftKey('n1', 'c')).toBe('note:n1')
  })
})
