import 'fake-indexeddb/auto'

import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { ReactNode } from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { clearOfflineQueue } from '~/lib/offline-queue'

import { makeNote } from '../lib/testing'
import { SaveToNotes } from './SaveToNotes'

const mocks = vi.hoisted(() => ({
  api: vi.fn(),
  flag: { value: true },
  notify: { clipSaved: vi.fn(), clipQueued: vi.fn(), error: vi.fn(), queued: vi.fn() },
}))

vi.mock('~/lib/api', async (importOriginal) => ({
  ...(await importOriginal<Record<string, unknown>>()),
  api: mocks.api,
}))
vi.mock('~/lib/supabase', () => ({
  getSupabase: () => ({ auth: { getSession: async () => ({ data: { session: { user: { id: 'u1' } } } }) } }),
}))
vi.mock('~/modules/observability', () => ({
  useFeatureFlag: () => mocks.flag.value,
  track: vi.fn(),
  ageBucket: () => '1-7d',
}))
vi.mock('~/modules/personalization', () => ({ useOnline: () => true }))
vi.mock('@tanstack/react-router', async () => (await import('~/test/router-stub')).routerStub)
vi.mock('../hooks/useNotesSync', () => ({ useNotesFlusher: () => ({ flush: async () => undefined }) }))
vi.mock('../lib/notify', () => ({ notify: mocks.notify, UNDO_MS: 10_000 }))

const wrapper = ({ children }: { children: ReactNode }) => (
  <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    {children}
  </QueryClientProvider>
)

const source = { module: 'syllabus', ref: 'itc', label: 'GST: ITC' }

beforeEach(async () => {
  vi.clearAllMocks()
  mocks.flag.value = true
  mocks.api.mockImplementation(async () => ({ note: makeNote(), created: true }))
  await clearOfflineQueue()
})

describe('SaveToNotes', () => {
  it('is hidden when the notes flag is off', () => {
    mocks.flag.value = false
    render(<SaveToNotes text="x" source={source} />, { wrapper })
    expect(screen.queryByRole('button')).toBeNull()
  })

  it('stays disabled without text', () => {
    render(<SaveToNotes text="  " source={source} />, { wrapper })
    expect(screen.getByRole('button', { name: /Save to notes/ })).toBeDisabled()
  })

  it('sends the text with its source, chapter and a client id, then offers to open the note', async () => {
    render(<SaveToNotes text="Blocked credits" source={source} chapterId="chapter-1" />, { wrapper })
    await userEvent.click(screen.getByRole('button', { name: /Save to notes/ }))
    await waitFor(() => expect(mocks.notify.clipSaved).toHaveBeenCalled())
    const [path, init] = mocks.api.mock.calls[0] as [string, { method: string; body: string }]
    expect(path).toBe('/notes/clips/')
    const body = JSON.parse(init.body)
    expect(body).toMatchObject({ text_md: 'Blocked credits', source, chapter_id: 'chapter-1', topic_id: null })
    expect(typeof body.client_id).toBe('string')
  })

  it('reuses the client id for the same text, so a second tap cannot make a second note', async () => {
    render(<SaveToNotes text="Same text" source={source} />, { wrapper })
    const button = screen.getByRole('button', { name: /Save to notes/ })
    await userEvent.click(button)
    await waitFor(() => expect(mocks.api).toHaveBeenCalledTimes(1))
    await userEvent.click(button)
    await waitFor(() => expect(mocks.api).toHaveBeenCalledTimes(2))
    const ids = mocks.api.mock.calls.map((c) => JSON.parse((c[1] as { body: string }).body).client_id)
    expect(ids[0]).toBe(ids[1])
  })
})
