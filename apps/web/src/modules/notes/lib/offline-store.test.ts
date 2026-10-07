import 'fake-indexeddb/auto'

import { beforeEach, describe, expect, it } from 'vitest'

import { buildLocalNote } from './local-note'
import {
  cachedNotes,
  cacheNote,
  clearDraft,
  clearUserData,
  draftKey,
  loadDraft,
  markNoteSynced,
  pickEmptyLocalNotes,
  pickEvictions,
  purgeEmptyLocalNotes,
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

describe('notes that only exist on this device', () => {
  const local = (id: string, over = {}) => ({ ...buildLocalNote(id), ...over })

  it('are flagged until the create is confirmed, then the flag goes and the rest stays', async () => {
    await cacheNote('u1', local('n1', { body_md: 'typed' }), { pending: true })
    expect((await readCachedNote('u1', 'n1'))?.note.local_only).toBe(true)
    await markNoteSynced('u1', 'n1')
    expect((await readCachedNote('u1', 'n1'))?.note).toMatchObject({ body_md: 'typed', local_only: undefined })
  })

  it('pickEmptyLocalNotes picks only old, empty, unqueued local notes of this user', () => {
    const entry = (id: string, over = {}, at = 0, userId = 'u1') => ({
      userId,
      note: local(id, over),
      lastOpenedAt: at,
      pending: true,
    })
    const entries = [
      entry('stale'),
      entry('fresh', {}, 100_000),
      entry('typed', { body_md: 'x' }),
      entry('queued'),
      entry('synced', { local_only: undefined }),
      entry('other', {}, 0, 'u2'),
    ]
    expect(pickEmptyLocalNotes(entries, 'u1', new Set(['queued']), 100_000 + 10)).toEqual(['stale'])
  })

  it('purgeEmptyLocalNotes forgets them and their empty draft', async () => {
    await cacheNote('u1', local('gone'), { pending: true, now: 0 })
    await saveDraft({
      userId: 'u1',
      key: 'note:gone',
      noteId: 'gone',
      clientId: 'gone',
      title: '',
      body: '',
      baseRev: 1,
      updatedAt: 0,
    })
    await purgeEmptyLocalNotes('u1', new Set(), 1_000_000)
    expect(await readCachedNote('u1', 'gone')).toBeUndefined()
    expect(await loadDraft('u1', 'note:gone')).toBeUndefined()
  })
})
