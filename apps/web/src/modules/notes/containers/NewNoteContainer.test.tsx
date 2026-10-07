import 'fake-indexeddb/auto'

import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { clearOfflineQueue, resetOfflineQueue } from '~/lib/offline-queue'

import { loadDraft, readCachedNote, resetOfflineStore, saveDraft } from '../lib/offline-store'
import { queuedNoteWrites } from '../lib/queue'
import { NewNoteContainer } from './NewNoteContainer'

const mocks = vi.hoisted(() => ({
  order: [] as string[],
  api: vi.fn(),
  navigate: vi.fn(),
  online: { value: true },
  overview: { value: { isPending: false, isError: false, isSuccess: true, data: undefined as unknown } },
}))

vi.mock('~/lib/api', async (importOriginal) => ({
  ...(await importOriginal<Record<string, unknown>>()),
  api: mocks.api,
}))
vi.mock('~/lib/supabase', () => ({
  getSupabase: () => ({ auth: { getSession: async () => ({ data: { session: { user: { id: 'u1' } } } }) } }),
}))
vi.mock('@tanstack/react-router', () => ({ useNavigate: () => mocks.navigate }))
vi.mock('~/modules/personalization', () => ({ useOnline: () => mocks.online.value }))
vi.mock('~/modules/coverage', () => ({ useChapterCoverage: () => ({ data: undefined, isPending: false }) }))
vi.mock('../hooks/useNotesQueries', () => ({ useChapterNotesOverview: () => mocks.overview.value }))
vi.mock('./NotesShell', () => ({ NotesShell: ({ children }: { children: ReactNode }) => <>{children}</> }))

const wrapper = ({ children }: { children: ReactNode }) => (
  <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    {children}
  </QueryClientProvider>
)

const OVERVIEW = {
  level_id: 'l1',
  subject: { id: 's1', key: 'tax', name: 'Taxation' },
  chapter: { id: 'c1', key: 'itc', name: 'ITC' },
}

beforeEach(async () => {
  vi.clearAllMocks()
  mocks.order.length = 0
  mocks.online.value = true
  mocks.overview.value = { isPending: false, isError: false, isSuccess: true, data: undefined }
  mocks.api.mockImplementation(async () => {
    mocks.order.push('network')
    return {}
  })
  mocks.navigate.mockImplementation(async () => void mocks.order.push('navigate'))
  resetOfflineStore()
  resetOfflineQueue()
  await clearOfflineQueue()
})

const noteIdOf = () => (mocks.navigate.mock.calls[0]?.[0] as { params: { noteId: string } }).params.noteId

describe('/app/notes/new is a doorway', () => {
  it('makes the id on this device and opens the editor at once, before any network call', async () => {
    render(<NewNoteContainer search={{}} />, { wrapper })
    await waitFor(() => expect(mocks.navigate).toHaveBeenCalledTimes(1))
    expect(mocks.navigate).toHaveBeenCalledWith(
      expect.objectContaining({ to: '/app/notes/n/$noteId', replace: true, search: {} }),
    )
    expect(noteIdOf()).toMatch(/^[0-9a-f-]{36}$/)
    expect(mocks.order).toEqual(['navigate'])
    expect(mocks.api).not.toHaveBeenCalled()
  })

  it('writes the local note first and queues nothing: an unused note creates nothing on the server', async () => {
    render(<NewNoteContainer search={{}} />, { wrapper })
    await waitFor(() => expect(mocks.navigate).toHaveBeenCalled())
    const cached = await readCachedNote('u1', noteIdOf())
    expect(cached?.note).toMatchObject({ title: '', body_md: '', rev: 1, local_only: true })
    expect(await queuedNoteWrites()).toHaveLength(0)
  })

  it('works offline: starts unfiled instead of waiting for the chapter lookup', async () => {
    mocks.online.value = false
    mocks.overview.value = { isPending: true, isError: false, isSuccess: false, data: undefined }
    render(<NewNoteContainer search={{ subject: 'tax', chapter: 'itc' }} />, { wrapper })
    await waitFor(() => expect(mocks.navigate).toHaveBeenCalledTimes(1))
    expect((await readCachedNote('u1', noteIdOf()))?.note.link.chapter_id).toBeNull()
    expect(mocks.api).not.toHaveBeenCalled()
  })

  it('files the note under the chapter of a ?chapter= link once the lookup is in', async () => {
    mocks.overview.value = { isPending: false, isError: false, isSuccess: true, data: OVERVIEW }
    render(<NewNoteContainer search={{ subject: 'tax', chapter: 'itc' }} />, { wrapper })
    await waitFor(() => expect(mocks.navigate).toHaveBeenCalledTimes(1))
    expect((await readCachedNote('u1', noteIdOf()))?.note.link).toMatchObject({ chapter_id: 'c1', chapter_key: 'itc' })
  })

  it('waits for the chapter lookup while it is loading, and opens once only', async () => {
    mocks.overview.value = { isPending: true, isError: false, isSuccess: false, data: undefined }
    const view = render(<NewNoteContainer search={{ subject: 'tax', chapter: 'itc' }} />, { wrapper })
    await new Promise((resolve) => setTimeout(resolve, 30))
    expect(mocks.navigate).not.toHaveBeenCalled()
    mocks.overview.value = { isPending: false, isError: true, isSuccess: false, data: undefined }
    view.rerender(<NewNoteContainer search={{ subject: 'tax', chapter: 'itc' }} />)
    await waitFor(() => expect(mocks.navigate).toHaveBeenCalledTimes(1))
    view.rerender(<NewNoteContainer search={{ subject: 'tax', chapter: 'itc' }} />)
    expect(mocks.navigate).toHaveBeenCalledTimes(1)
  })

  it('adopts a draft that an older version left behind as a recovered draft of the new note', async () => {
    await saveDraft({
      userId: 'u1',
      key: 'new:abc',
      noteId: null,
      clientId: 'abc',
      title: 'Half written',
      body: 'text',
      baseRev: null,
      updatedAt: Date.now(),
    })
    render(<NewNoteContainer search={{}} />, { wrapper })
    await waitFor(() => expect(mocks.navigate).toHaveBeenCalledTimes(1))
    const id = noteIdOf()
    expect(await loadDraft('u1', `note:${id}`)).toMatchObject({ title: 'Half written', body: 'text', noteId: id })
    expect(await loadDraft('u1', 'new:abc')).toBeUndefined()
  })
})
