import 'fake-indexeddb/auto'

import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '~/lib/api'
import { clearOfflineQueue, resetFlushState, resetOfflineQueue } from '~/lib/offline-queue'

import { buildLocalNote } from './local-note'
import { cacheNote, loadDraft, readCachedNote, resetOfflineStore, saveDraft } from './offline-store'
import {
  createKey,
  createNoteOrQueue,
  deleteNoteOrQueue,
  ensureCreateQueued,
  flushNotes,
  patchNoteOrQueue,
  queuedNoteWrites,
  resetReplacedIds,
  setNoteTagsAfterCreate,
  tagsKey,
} from './queue'

const mocks = vi.hoisted(() => ({ api: vi.fn(), online: { value: true } }))
vi.mock('~/lib/api', async (importOriginal) => ({
  ...(await importOriginal<Record<string, unknown>>()),
  api: mocks.api,
}))
vi.mock('~/lib/supabase', () => ({
  getSupabase: () => ({ auth: { getSession: async () => ({ data: { session: { user: { id: 'u1' } } } }) } }),
}))

const ID = '3f2b8c1e-5a4d-4e9b-8c7a-1d2e3f4a5b6c'
const setOnline = (value: boolean) => Object.defineProperty(navigator, 'onLine', { value, configurable: true })

interface Sent {
  method: string
  path: string
  body?: Record<string, unknown>
}
let sent: Sent[]
let answer: (call: Sent) => unknown

beforeEach(async () => {
  sent = []
  setOnline(true)
  answer = () => ({})
  mocks.api.mockImplementation(async (path: string, init?: { method?: string; body?: string }) => {
    const call = { path, method: init?.method ?? 'GET', body: init?.body ? JSON.parse(init.body) : undefined }
    sent.push(call)
    return answer(call)
  })
  resetOfflineStore()
  resetOfflineQueue()
  resetFlushState()
  resetReplacedIds()
  await clearOfflineQueue()
})

const offline = () => setOnline(false)
/** Lets the background flushes started while offline finish (they find nothing to do) before the network is back. */
const reconnect = async () => {
  await new Promise((resolve) => setTimeout(resolve, 20))
  setOnline(true)
}
const methods = () => sent.map((c) => `${c.method} ${c.path}`)

describe('creating a note with an id the client chose', () => {
  it('online: one idempotent PUT, nothing queued', async () => {
    const result = await createNoteOrQueue(ID, { title: 'T', body_md: 'b', chapter_id: null, topic_id: null })
    expect(result.status).toBe('saved')
    expect(sent).toEqual([
      {
        method: 'PUT',
        path: `/notes/${ID}/`,
        body: { client_id: ID, title: 'T', body_md: 'b', chapter_id: null, topic_id: null },
      },
    ])
    expect(await queuedNoteWrites()).toHaveLength(0)
  })

  it('offline: queues the create and folds later saves into it instead of piling up', async () => {
    offline()
    const first = await createNoteOrQueue(ID, { title: 'T', body_md: 'a' })
    const second = await createNoteOrQueue(ID, { title: 'T', body_md: 'a b' })
    expect([first, second]).toEqual([
      { status: 'queued', fresh: true },
      { status: 'queued', fresh: false },
    ])
    const waiting = await queuedNoteWrites()
    expect(waiting).toHaveLength(1)
    expect(waiting[0]).toMatchObject({
      clientId: createKey(ID),
      method: 'PUT',
      body: { client_id: ID, body_md: 'a b' },
    })
    expect(sent).toHaveLength(0)
  })

  it('replaying the queue twice sends the create once, and a repeated PUT is harmless (200)', async () => {
    offline()
    await createNoteOrQueue(ID, { title: 'T', body_md: 'a' })
    await reconnect()
    await flushNotes()
    await flushNotes()
    expect(methods()).toEqual([`PUT /notes/${ID}/`])
    expect(await queuedNoteWrites()).toHaveLength(0)
  })

  it('a full quota (429) is shown at once and is not kept in the queue to retry', async () => {
    answer = () => {
      throw new ApiError(429, 'x', {
        error: { code: 'quota_exceeded', details: { kind: 'notes', used: 1, limit: 1, plan: 'free' } },
      })
    }
    await expect(createNoteOrQueue(ID, { body_md: 'a' })).rejects.toMatchObject({ status: 429 })
    expect(await queuedNoteWrites()).toHaveLength(0)
  })

  it('a throttled 429 (not the quota) is kept and retried later', async () => {
    answer = () => {
      throw new ApiError(429, 'slow down', { error: { code: 'throttled' } })
    }
    expect((await createNoteOrQueue(ID, { body_md: 'a' })).status).toBe('queued')
    expect(await queuedNoteWrites()).toHaveLength(1)
  })
})

describe('replay order: create, then tags, then edits', () => {
  it('keeps the order even when everything was queued in the same millisecond', async () => {
    vi.spyOn(Date, 'now').mockReturnValue(1_000)
    offline()
    const note = { ...buildLocalNote(ID), title: 'T', body_md: 'a' }
    await cacheNote('u1', note, { pending: true })
    // Tags and a pin before any text was saved: the create is queued first by the tag write itself.
    const { createdFresh } = await setNoteTagsAfterCreate(note, ['tag-1'])
    await patchNoteOrQueue(ID, { base_rev: 1, title: 'T2', body_md: 'a b', source: 'autosave' })
    await patchNoteOrQueue(ID, { base_rev: 1, body_md: 'a b c', source: 'autosave' })
    expect(createdFresh).toBe(true)
    expect((await queuedNoteWrites()).map((e) => e.clientId)).toEqual([createKey(ID), tagsKey(ID), `patch:${ID}`])

    await reconnect()
    vi.restoreAllMocks()
    await flushNotes()
    expect(methods()).toEqual([`PUT /notes/${ID}/`, 'PUT /notes/items/tags/', `PATCH /notes/${ID}/`])
    expect(sent[1]?.body).toEqual({ item_type: 'note', item_id: ID, tag_ids: ['tag-1'] })
    expect(sent[2]?.body).toMatchObject({ base_rev: 1, body_md: 'a b c', title: 'T2' })
  })

  it('a newer tag set replaces the waiting one in place', async () => {
    offline()
    const note = { ...buildLocalNote(ID), body_md: 'a' }
    await setNoteTagsAfterCreate(note, ['a'])
    const again = await setNoteTagsAfterCreate(note, ['a', 'b'])
    expect(again.createdFresh).toBe(false)
    const tags = (await queuedNoteWrites()).filter((e) => e.clientId === tagsKey(ID))
    expect(tags).toHaveLength(1)
    expect(tags[0]?.body.tag_ids).toEqual(['a', 'b'])
  })

  it('a parked conflict on the edit does not stop the writes behind it', async () => {
    offline()
    const note = { ...buildLocalNote(ID), body_md: 'a' }
    await ensureCreateQueued(note)
    await patchNoteOrQueue(ID, { base_rev: 1, body_md: 'x', source: 'autosave' })
    await setNoteTagsAfterCreate(note, ['t'])
    await reconnect()
    answer = (call) => {
      if (call.method === 'PATCH')
        throw new ApiError(409, 'c', {
          error: { code: 'note_conflict', details: { theirs: { rev: 2 }, mine: {}, merged: null } },
        })
      return {}
    }
    const result = await flushNotes()
    expect(result).toMatchObject({ sent: 2, parked: 1 })
    expect(methods()).toEqual([`PUT /notes/${ID}/`, `PATCH /notes/${ID}/`, 'PUT /notes/items/tags/'])
  })
})

describe('offline create, reload, reconnect', () => {
  it('a reload loses nothing: the queue and the local note come back from the device', async () => {
    offline()
    const note = { ...buildLocalNote(ID), body_md: 'typed offline' }
    await cacheNote('u1', note, { pending: true })
    await createNoteOrQueue(ID, { body_md: 'typed offline' })
    resetOfflineStore() // the page reloads: nothing is held in memory any more
    resetOfflineQueue()
    resetFlushState()
    expect((await readCachedNote('u1', ID))?.note).toMatchObject({ body_md: 'typed offline', local_only: true })
    expect(await queuedNoteWrites()).toHaveLength(1)

    await reconnect()
    await flushNotes()
    expect(methods()).toEqual([`PUT /notes/${ID}/`])
    expect((await readCachedNote('u1', ID))?.note.local_only).toBeUndefined() // no longer only here
  })

  it('two tabs: the tab that does not hold the flush lock sends nothing, the other sends the create once', async () => {
    offline()
    await createNoteOrQueue(ID, { body_md: 'a' })
    await reconnect()
    const lockedByOtherTab = {
      request: async (_n: string, _o: unknown, task: (l: null) => Promise<unknown>) => task(null),
    }
    const free = { request: async (_n: string, _o: unknown, task: (l: object) => Promise<unknown>) => task({}) }
    try {
      Object.defineProperty(navigator, 'locks', { value: lockedByOtherTab, configurable: true })
      expect(await flushNotes()).toMatchObject({ busy: true, sent: 0, remaining: 1 })
      expect(sent).toHaveLength(0)
      Object.defineProperty(navigator, 'locks', { value: free, configurable: true })
      expect(await flushNotes()).toMatchObject({ sent: 1 })
      expect(methods()).toEqual([`PUT /notes/${ID}/`])
    } finally {
      Object.defineProperty(navigator, 'locks', { value: undefined, configurable: true })
    }
  })
})

describe('a create that answers 404 (the id is another student’s)', () => {
  it('gets a fresh id once; the draft, the copy and the waiting writes follow it', async () => {
    offline()
    const note = { ...buildLocalNote(ID), body_md: 'mine' }
    await cacheNote('u1', note, { pending: true })
    await saveDraft({
      userId: 'u1',
      key: `note:${ID}`,
      noteId: ID,
      clientId: ID,
      title: '',
      body: 'mine',
      baseRev: 1,
      updatedAt: 1,
    })
    await createNoteOrQueue(ID, { body_md: 'mine' })
    await setNoteTagsAfterCreate(note, ['t'])
    await reconnect()
    let first = true
    answer = (call) => {
      if (first && call.path === `/notes/${ID}/`) {
        first = false
        throw new ApiError(404, 'nf', { error: { code: 'not_found' } })
      }
      return {}
    }
    const rekeyed = vi.fn()
    await flushNotes({ onRekeyed: rekeyed })

    expect(rekeyed).toHaveBeenCalledTimes(1)
    const newId = rekeyed.mock.calls[0]?.[1] as string
    expect(newId).not.toBe(ID)
    expect(methods()).toEqual([`PUT /notes/${ID}/`, `PUT /notes/${newId}/`, 'PUT /notes/items/tags/'])
    expect(sent[2]?.body).toMatchObject({ item_id: newId })
    expect(await readCachedNote('u1', ID)).toBeUndefined()
    expect((await readCachedNote('u1', newId))?.note).toMatchObject({ id: newId, body_md: 'mine' })
    expect(await loadDraft('u1', `note:${newId}`)).toMatchObject({ body: 'mine', noteId: newId })
    expect(await queuedNoteWrites()).toHaveLength(0)
  })

  it('a second 404 is not retried again: the create is dropped like any refused write', async () => {
    offline()
    await createNoteOrQueue(ID, { body_md: 'mine' })
    await reconnect()
    answer = () => {
      throw new ApiError(404, 'nf', { error: { code: 'not_found' } })
    }
    const dropped = vi.fn()
    const result = await flushNotes({ onDropped: dropped })
    expect(result?.dropped).toBe(1)
    expect(sent).toHaveLength(2)
  })
})

describe('deleting a note the server never saw', () => {
  it('drops its queued writes and sends nothing', async () => {
    offline()
    const note = { ...buildLocalNote(ID), body_md: 'a' }
    await cacheNote('u1', note, { pending: true })
    await saveDraft({
      userId: 'u1',
      key: `note:${ID}`,
      noteId: ID,
      clientId: ID,
      title: '',
      body: 'a',
      baseRev: 1,
      updatedAt: 1,
    })
    await createNoteOrQueue(ID, { body_md: 'a' })
    await setNoteTagsAfterCreate(note, ['t'])
    await patchNoteOrQueue(ID, { base_rev: 1, pinned: true, source: 'manual' })

    expect(await deleteNoteOrQueue(ID)).toEqual({ status: 'discarded' })
    expect(await queuedNoteWrites()).toHaveLength(0)
    expect(await readCachedNote('u1', ID)).toBeUndefined()
    expect(await loadDraft('u1', `note:${ID}`)).toBeUndefined()
    await reconnect()
    await flushNotes()
    expect(sent).toHaveLength(0)
  })

  it('a note the server knows is deleted the normal way', async () => {
    await cacheNote('u1', { ...buildLocalNote(ID), local_only: undefined }, {})
    const result = await deleteNoteOrQueue(ID)
    expect(result.status).toBe('saved')
    expect(methods()).toEqual([`DELETE /notes/${ID}/`])
  })
})
