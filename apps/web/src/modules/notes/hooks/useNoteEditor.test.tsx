import 'fake-indexeddb/auto'

import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, renderHook, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '~/lib/api'
import { clearOfflineQueue, resetOfflineQueue } from '~/lib/offline-queue'

import { resetOfflineStore, saveDraft } from '../lib/offline-store'
import { makeNote } from '../lib/testing'
import { useNoteEditor } from './useNoteEditor'

const mocks = vi.hoisted(() => ({ api: vi.fn(), online: { value: true } }))

vi.mock('~/lib/api', async (importOriginal) => ({
  ...(await importOriginal<Record<string, unknown>>()),
  api: mocks.api,
}))
vi.mock('~/lib/supabase', () => ({
  getSupabase: () => ({ auth: { getSession: async () => ({ data: { session: { user: { id: 'u1' } } } }) } }),
}))
vi.mock('~/modules/personalization', () => ({ useOnline: () => mocks.online.value }))
vi.mock('~/modules/coverage', () => ({
  useOverview: () => ({ data: undefined }),
  useSubjectCoverage: () => ({ data: undefined }),
  useChapterCoverage: () => ({ data: undefined }),
}))
vi.mock('~/modules/observability', () => ({ track: vi.fn(), ageBucket: () => '1-7d' }))
vi.mock('../lib/notify', () => ({
  notify: new Proxy({}, { get: () => vi.fn() }),
  UNDO_MS: 10_000,
}))

const NOTE = makeNote({
  id: '11111111-1111-4111-8111-111111111111',
  rev: 2,
  title: 'GST',
  body_md: 'first line',
  updated_at: '2026-10-01T10:00:00Z',
})
const USAGE = {
  plan: 'free',
  limits: { max_storage_mb: 500, max_notes: 2000, max_note_chars: 100000, max_note_images: 40, max_tags: 200 },
  used: { storage_bytes: 0, notes: 3, tags: 0 },
  resets_on: '2026-11-01',
}

interface Call {
  path: string
  method: string
  body?: Record<string, unknown>
}
let calls: Call[]
let respond: (call: Call) => unknown

function wrapper({ children }: { children: ReactNode }) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>
}

const patches = () => calls.filter((c) => c.method === 'PATCH')

beforeEach(async () => {
  calls = []
  mocks.online.value = true
  Object.defineProperty(navigator, 'onLine', { value: true, configurable: true })
  respond = (call) => {
    if (call.path === '/notes/usage/') return USAGE
    if (call.method === 'GET' && call.path === `/notes/${NOTE.id}/`) return NOTE
    if (call.method === 'PATCH') return { ...NOTE, rev: 3, ...call.body }
    if (call.method === 'POST' && call.path === '/notes/')
      return { ...NOTE, id: '22222222-2222-4222-8222-222222222222', rev: 1, ...call.body }
    throw new Error(`unexpected ${call.method} ${call.path}`)
  }
  mocks.api.mockImplementation(async (path: string, init?: { method?: string; body?: string }) => {
    const call: Call = { path, method: init?.method ?? 'GET', body: init?.body ? JSON.parse(init.body) : undefined }
    calls.push(call)
    return respond(call)
  })
  resetOfflineStore()
  resetOfflineQueue()
  await clearOfflineQueue()
})

afterEach(() => {
  vi.useRealTimers()
})

async function openExisting() {
  const hook = renderHook(() => useNoteEditor({ noteId: NOTE.id }), { wrapper })
  await waitFor(() => expect(hook.result.current.status).toBe('ready'))
  return hook
}

describe('useNoteEditor: an existing note', () => {
  it('opens with the note text', async () => {
    const { result } = await openExisting()
    expect(result.current.title).toBe('GST')
    expect(result.current.body).toBe('first line')
    expect(result.current.recovered).toBe(false)
  })

  it('saves two seconds after typing stops, with the revision and the text it was based on', async () => {
    const { result } = await openExisting()
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] })
    act(() => result.current.setBody('first line\nsecond'))
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1900)
    })
    expect(patches()).toHaveLength(0)
    await act(async () => {
      await vi.advanceTimersByTimeAsync(200)
    })
    vi.useRealTimers()
    await waitFor(() => expect(patches()).toHaveLength(1))
    expect(patches()[0]?.body).toMatchObject({
      base_rev: 2,
      base_body_md: 'first line',
      body_md: 'first line\nsecond',
      title: 'GST',
      source: 'autosave',
    })
  })

  it('saves at once with Save now, and uses the new revision for the next save', async () => {
    const { result } = await openExisting()
    act(() => result.current.setBody('one'))
    await act(async () => {
      await result.current.saveNow()
    })
    await waitFor(() => expect(patches()).toHaveLength(1))
    act(() => result.current.setBody('two'))
    await act(async () => {
      await result.current.saveNow()
    })
    await waitFor(() => expect(patches()).toHaveLength(2))
    expect(patches()[1]?.body).toMatchObject({ base_rev: 3, base_body_md: 'one', body_md: 'two' })
  })

  it('shows the merged text when the server merged a stale save', async () => {
    const { result } = await openExisting()
    respond = (call) =>
      call.method === 'PATCH'
        ? { ...NOTE, rev: 5, body_md: 'merged text', merged: true }
        : call.path === '/notes/usage/'
          ? USAGE
          : NOTE
    act(() => result.current.setBody('mine'))
    await act(async () => {
      await result.current.saveNow()
    })
    await waitFor(() => expect(result.current.body).toBe('merged text'))
  })

  it('stops saving on a conflict, and settles it with the server revision and the chosen resolution', async () => {
    const { result } = await openExisting()
    const details = {
      theirs: { rev: 4, title: 'GST', body_md: 'their text', updated_at: '2026-10-02T00:00:00Z' },
      mine: { body_md: 'mine' },
      merged: null,
    }
    respond = (call) => {
      if (call.method === 'PATCH' && call.body?.resolution === undefined) {
        throw new ApiError(409, 'conflict', { error: { code: 'note_conflict', message: 'x', details } })
      }
      return call.method === 'PATCH'
        ? { ...NOTE, rev: 5, body_md: 'their text\n\n---\n\nmine' }
        : call.path === '/notes/usage/'
          ? USAGE
          : NOTE
    }
    act(() => result.current.setBody('mine'))
    await act(async () => {
      await result.current.saveNow()
    })
    await waitFor(() => expect(result.current.conflict).not.toBeNull())
    expect(result.current.conflict?.mine.body).toBe('mine')

    // Typing more does not send anything while the conflict is open.
    act(() => result.current.setBody('mine, more'))
    await act(async () => {
      await result.current.saveNow()
    })
    expect(patches()).toHaveLength(1)

    await act(async () => {
      await result.current.resolveConflict('both')
    })
    expect(patches()[1]?.body).toMatchObject({ base_rev: 4, resolution: 'both', source: 'manual' })
    await waitFor(() => expect(result.current.conflict).toBeNull())
  })

  it('does not send text the server would refuse, and says what to fix', async () => {
    const { result } = await openExisting()
    act(() => result.current.setBody('[bad](javascript:alert(1))'))
    await act(async () => {
      await result.current.saveNow()
    })
    await waitFor(() => expect(result.current.problems?.kind).toBe('lint'))
    expect(patches()).toHaveLength(0)
  })

  it('queues the save offline instead of failing, and keeps the text', async () => {
    const { result } = await openExisting()
    Object.defineProperty(navigator, 'onLine', { value: false, configurable: true })
    act(() => result.current.setBody('written offline'))
    await act(async () => {
      await result.current.saveNow()
    })
    expect(patches()).toHaveLength(0)
    expect(result.current.body).toBe('written offline')
    expect(result.current.saveFailed).toBe(false)
  })

  it('restores a draft that is newer than the server copy and says so', async () => {
    await saveDraft({
      userId: 'u1',
      key: `note:${NOTE.id}`,
      noteId: NOTE.id,
      clientId: '',
      title: 'GST',
      body: 'typed before the crash',
      baseRev: 2,
      baseBody: 'first line',
      updatedAt: new Date('2026-10-03T00:00:00Z').getTime(),
    })
    const { result } = await openExisting()
    expect(result.current.body).toBe('typed before the crash')
    expect(result.current.recovered).toBe(true)
  })

  it('ignores a draft that is older than the server copy', async () => {
    await saveDraft({
      userId: 'u1',
      key: `note:${NOTE.id}`,
      noteId: NOTE.id,
      clientId: '',
      title: 'GST',
      body: 'stale',
      baseRev: 1,
      updatedAt: new Date('2026-09-01T00:00:00Z').getTime(),
    })
    const { result } = await openExisting()
    expect(result.current.body).toBe('first line')
    expect(result.current.recovered).toBe(false)
  })
})

describe('useNoteEditor: a new note', () => {
  it('sends nothing while empty, then creates once with a client id and tells the screen', async () => {
    const onCreated = vi.fn()
    const { result } = renderHook(() => useNoteEditor({ noteId: null, onCreated }), { wrapper })
    await waitFor(() => expect(result.current.status).toBe('ready'))
    await act(async () => {
      await result.current.saveNow()
    })
    expect(calls.filter((c) => c.method === 'POST')).toHaveLength(0)

    act(() => {
      result.current.setTitle('Idea')
      result.current.setBody('body')
    })
    await act(async () => {
      await result.current.saveNow()
    })
    await waitFor(() => expect(onCreated).toHaveBeenCalledTimes(1))
    const created = calls.find((c) => c.method === 'POST' && c.path === '/notes/')
    expect(created?.body).toMatchObject({ title: 'Idea', body_md: 'body', chapter_id: null })
    expect(typeof created?.body?.client_id).toBe('string')
  })

  it('files a new note under the prefilled chapter', async () => {
    const prefill = {
      levelId: 'l',
      subjectId: 's',
      subjectKey: 'tax',
      subjectName: 'Taxation',
      chapterId: 'chapter-1',
      chapterKey: 'itc',
      chapterName: 'ITC',
      topicId: null,
      topicKey: null,
      topicName: null,
    }
    const { result } = renderHook(() => useNoteEditor({ noteId: null, prefill }), { wrapper })
    await waitFor(() => expect(result.current.status).toBe('ready'))
    act(() => result.current.setBody('x'))
    await act(async () => {
      await result.current.saveNow()
    })
    await waitFor(() => expect(calls.some((c) => c.method === 'POST')).toBe(true))
    expect(calls.find((c) => c.method === 'POST')?.body).toMatchObject({ chapter_id: 'chapter-1', topic_id: null })
  })

  it('brings back an unsaved draft of a new note', async () => {
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
    const { result } = renderHook(() => useNoteEditor({ noteId: null }), { wrapper })
    await waitFor(() => expect(result.current.recovered).toBe(true))
    expect(result.current.title).toBe('Half written')
  })
})
