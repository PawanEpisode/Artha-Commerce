import 'fake-indexeddb/auto'

import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, renderHook } from '@testing-library/react'
import type { ReactNode } from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { clearOfflineQueue, resetOfflineQueue } from '~/lib/offline-queue'
import { track } from '~/modules/observability'

import { notesKeys } from '../lib/keys'
import { buildLocalNote } from '../lib/local-note'
import { cacheNote, readCachedNote, resetOfflineStore } from '../lib/offline-store'
import { queuedNoteWrites } from '../lib/queue'
import { useNoteActions } from './useNoteActions'

const mocks = vi.hoisted(() => ({
  api: vi.fn(),
  notify: { queued: vi.fn(), discarded: vi.fn(), trashed: vi.fn(), error: vi.fn() },
}))
vi.mock('~/lib/api', async (importOriginal) => ({
  ...(await importOriginal<Record<string, unknown>>()),
  api: mocks.api,
}))
vi.mock('~/lib/supabase', () => ({
  getSupabase: () => ({ auth: { getSession: async () => ({ data: { session: { user: { id: 'u1' } } } }) } }),
}))
vi.mock('~/modules/observability', () => ({ track: vi.fn(), ageBucket: () => '1-7d' }))
vi.mock('../lib/notify', () => ({ notify: mocks.notify, UNDO_MS: 10_000 }))

const ID = '3f2b8c1e-5a4d-4e9b-8c7a-1d2e3f4a5b6c'
const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
const wrapper = ({ children }: { children: ReactNode }) => (
  <QueryClientProvider client={client}>{children}</QueryClientProvider>
)

beforeEach(async () => {
  vi.clearAllMocks()
  Object.defineProperty(navigator, 'onLine', { value: false, configurable: true })
  mocks.api.mockRejectedValue(new TypeError('offline'))
  resetOfflineStore()
  resetOfflineQueue()
  await clearOfflineQueue()
  client.clear()
  const note = { ...buildLocalNote(ID), title: 'Idea', body_md: 'text' }
  await cacheNote('u1', note, { pending: true })
  client.setQueryData(notesKeys.note(ID), note)
})

describe('useNoteActions on a note the server has not seen', () => {
  it('tags before the first save: queues the create, then the tag set behind it, and counts one note_created', async () => {
    const { result } = renderHook(() => useNoteActions(), { wrapper })
    const note = client.getQueryData<ReturnType<typeof buildLocalNote>>(notesKeys.note(ID))!
    await act(async () => {
      await result.current.change(note, { tagIds: ['t1'], tags: [{ id: 't1', name: 'doubt', color_key: null }] })
      await result.current.change(note, { tagIds: ['t1', 't2'] })
    })
    const queued = await queuedNoteWrites()
    expect(queued.map((e) => `${e.method} ${e.path}`)).toEqual([`PUT /notes/${ID}/`, 'PUT /notes/items/tags/'])
    expect(queued[1]?.body.tag_ids).toEqual(['t1', 't2'])
    expect(vi.mocked(track).mock.calls.filter(([name]) => name === 'note_created')).toHaveLength(1)
    expect(JSON.stringify(vi.mocked(track).mock.calls)).not.toContain(ID)
    expect((await readCachedNote('u1', ID))?.note).toMatchObject({ local_only: true, tags: [{ id: 't1' }] })
  })

  it('deleting it drops the queue entries, says it was only here and offers no undo', async () => {
    const { result } = renderHook(() => useNoteActions(), { wrapper })
    const note = client.getQueryData<ReturnType<typeof buildLocalNote>>(notesKeys.note(ID))!
    await act(async () => {
      await result.current.change(note, { tagIds: ['t1'] })
      await result.current.trash(note)
    })
    expect(await queuedNoteWrites()).toHaveLength(0)
    expect(mocks.notify.discarded).toHaveBeenCalledTimes(1)
    expect(mocks.notify.trashed).not.toHaveBeenCalled()
    expect(mocks.api).not.toHaveBeenCalled()
  })
})
