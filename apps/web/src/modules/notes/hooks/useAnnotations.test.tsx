import 'fake-indexeddb/auto'

import { act, renderHook, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { clearOfflineQueue, resetFlushState, resetOfflineQueue } from '~/lib/offline-queue'
import type * as Observability from '~/modules/observability'

import { resetAnnotationQueue, waitingWrites } from '../lib/annotation-queue'
import { clearAnnotationData, resetAnnotationStore } from '../lib/annotation-store'
import { DOC, makeAnnotation } from '../lib/annotation-testing'
import type { BatchOpBody, MarkDraft } from '../lib/annotation-types'
import type * as AnnotationsApi from '../lib/annotations-api'
import { UNFILED_LINK } from '../lib/testing'
import { useAnnotations } from './useAnnotations'

const api = vi.hoisted(() => ({ getDelta: vi.fn(), batchMarks: vi.fn(), putMark: vi.fn(), makeCard: vi.fn() }))
const notify = vi.hoisted(() => ({
  deleted: vi.fn(),
  overwritten: vi.fn(),
  editWins: vi.fn(),
  limitReached: vi.fn(),
  dropped: vi.fn(),
  cardNeedsConnection: vi.fn(),
  cardCreated: vi.fn(),
  cardNoText: vi.fn(),
  cardUnavailable: vi.fn(),
  cardFailed: vi.fn(),
}))
vi.mock('../lib/annotations-api', async (original) => ({
  ...(await original<typeof AnnotationsApi>()),
  ...api,
}))
vi.mock('../lib/annotation-notify', () => ({ markNotify: notify }))
vi.mock('~/modules/observability', async (original) => ({
  ...(await original<typeof Observability>()),
  track: vi.fn(),
}))
vi.mock('~/lib/supabase', () => ({
  getSupabase: () => ({ auth: { getSession: async () => ({ data: { session: { user: { id: 'u1' } } } }) } }),
}))

const draft = (page = 3): MarkDraft => ({
  kind: 'highlight',
  page,
  geometry: { quads: [[0.1, 0.1, 0.4, 0.02]] },
  color: 'y',
})
const doc = { id: DOC, ranges: [], link: UNFILED_LINK }
const sent = () => api.batchMarks.mock.calls.flatMap(([, ops]) => ops as BatchOpBody[])
const onLine = vi.spyOn(window.navigator, 'onLine', 'get')

/** A server that remembers: the marks it was sent, a change_seq per write, and a delta feed over them. */
const server = new Map<string, ReturnType<typeof makeAnnotation>>()
let seq = 0
const startFakeServer = () => {
  server.clear()
  seq = 0
  api.getDelta.mockImplementation(async (_doc: string, since: number) => ({
    items: [...server.values()].filter((a) => a.seq > since),
    change_seq: seq,
    next_since_seq: seq,
    has_more: false,
  }))
  api.batchMarks.mockImplementation(async (_doc: string, ops: BatchOpBody[]) => ({
    change_seq: seq,
    marks: { count: server.size, limit: 20_000, near_limit: false },
    results: ops.map((op) => {
      seq += 1
      const before = server.get(op.id)
      const next = makeAnnotation({
        ...(before ?? {}),
        id: op.id,
        document_id: DOC,
        page: (op.page as number) ?? before?.page ?? 1,
        rev: (before?.rev ?? 0) + 1,
        seq,
        deleted_at: op.op === 'delete' ? '2026-10-08T10:00:00Z' : null,
      })
      server.set(op.id, next)
      return { id: op.id, status: 'ok' as const, annotation: next }
    }),
  }))
}

beforeEach(async () => {
  onLine.mockReturnValue(true)
  startFakeServer()
  resetOfflineQueue()
  resetFlushState()
  resetAnnotationQueue()
  resetAnnotationStore()
  await clearAnnotationData('u1')
  await clearOfflineQueue()
})
afterEach(() => {
  vi.clearAllMocks()
  vi.useRealTimers()
})

const open = async () => {
  const hook = renderHook(() => useAnnotations(doc))
  await waitFor(() => expect(hook.result.current.status).toBe('ready'))
  return hook
}

describe('local first (ERD decision 9)', () => {
  it('shows a new mark in the same tick and has it saved on this device in well under 100 ms', async () => {
    onLine.mockReturnValue(false)
    const { result } = await open()
    const started = performance.now()
    act(() => void result.current.add(draft()))
    const visibleAfter = performance.now() - started
    expect(result.current.marks).toHaveLength(1)
    await waitFor(async () => expect(await waitingWrites(DOC)).toHaveLength(1))
    const savedAfter = performance.now() - started
    expect(visibleAfter).toBeLessThan(100)
    expect(savedAfter).toBeLessThan(100)
    expect(api.batchMarks).not.toHaveBeenCalled()
  })

  it('makes 12 marks offline, survives a reload, and sends them once, in order, when the connection returns', async () => {
    onLine.mockReturnValue(false)
    const first = await open()
    const ids: string[] = []
    act(() => {
      for (let n = 1; n <= 12; n++) ids.push(first.result.current.add(draft(n))?.id ?? '')
    })
    await waitFor(async () => expect(await waitingWrites(DOC)).toHaveLength(12))
    expect(first.result.current.sync).toMatchObject({ state: 'offline', count: 12 })
    first.unmount()

    // Reload: the marks come back from the queue, nothing is lost and nothing was sent.
    const second = await open()
    await waitFor(() => expect(second.result.current.marks).toHaveLength(12))
    expect(api.batchMarks).not.toHaveBeenCalled()

    onLine.mockReturnValue(true)
    act(() => void window.dispatchEvent(new Event('online')))
    await waitFor(() => expect(api.batchMarks).toHaveBeenCalledTimes(1))
    expect(sent().map((op) => op.id)).toEqual(ids)
    await waitFor(async () => expect(await waitingWrites(DOC)).toHaveLength(0))
    await waitFor(() => expect(second.result.current.sync.state).toBe('saved'))
    expect(second.result.current.marks).toHaveLength(12)
    expect(server.size).toBe(12)

    act(() => void window.dispatchEvent(new Event('online')))
    await new Promise((r) => setTimeout(r, 50))
    expect(api.batchMarks).toHaveBeenCalledTimes(1)
    expect(server.size).toBe(12)
    expect(second.result.current.marks).toHaveLength(12)
  })

  it('a mark made and deleted offline is never sent', async () => {
    onLine.mockReturnValue(false)
    const { result } = await open()
    let id = ''
    act(() => void (id = result.current.add(draft())?.id ?? ''))
    await waitFor(async () => expect(await waitingWrites(DOC)).toHaveLength(1))
    act(() => result.current.remove(id, { silent: true }))
    await waitFor(async () => expect(await waitingWrites(DOC)).toHaveLength(0))
    expect(result.current.marks).toHaveLength(0)
  })
})

describe('delta sync', () => {
  it('pulls what changed elsewhere on open, with tombstones, and resumes from next_since_seq', async () => {
    api.getDelta.mockResolvedValueOnce({
      items: [
        makeAnnotation({ id: 'a', seq: 4 }),
        makeAnnotation({ id: 'b', seq: 5, deleted_at: '2026-10-07T00:00:00Z' }),
      ],
      change_seq: 5,
      next_since_seq: 5,
      has_more: false,
    })
    const { result } = await open()
    await waitFor(() => expect(result.current.marks.map((m) => m.id)).toEqual(['a']))
    expect(api.getDelta).toHaveBeenCalledWith(DOC, 0)
    act(() => void result.current.syncNow())
    await waitFor(() => expect(api.getDelta).toHaveBeenLastCalledWith(DOC, 5))
  })

  it('syncs again every 30 seconds in the foreground and when the tab comes back, never in the background', async () => {
    const timers = vi.spyOn(window, 'setInterval')
    const { result } = await open()
    expect(result.current.status).toBe('ready')
    const tick = timers.mock.calls.find(([, ms]) => ms === 30_000)?.[0] as () => void
    expect(tick).toBeTypeOf('function')
    const base = api.getDelta.mock.calls.length
    await act(async () => tick())
    await waitFor(() => expect(api.getDelta.mock.calls.length).toBeGreaterThan(base))
    const afterTick = api.getDelta.mock.calls.length
    Object.defineProperty(document, 'visibilityState', { value: 'hidden', configurable: true })
    await act(async () => tick())
    await new Promise((r) => setTimeout(r, 30))
    expect(api.getDelta.mock.calls.length).toBe(afterTick)
    Object.defineProperty(document, 'visibilityState', { value: 'visible', configurable: true })
    act(() => void document.dispatchEvent(new Event('visibilitychange')))
    await waitFor(() => expect(api.getDelta.mock.calls.length).toBeGreaterThan(afterTick))
  })
})

describe('delete with Undo', () => {
  it('deletes at once, offers Undo, and Undo before the send cancels the delete', async () => {
    onLine.mockReturnValue(false)
    const { result } = await open()
    let id = ''
    act(() => void (id = result.current.add(draft())?.id ?? ''))
    await waitFor(async () => expect(await waitingWrites(DOC)).toHaveLength(1))
    onLine.mockReturnValue(true)
    act(() => void window.dispatchEvent(new Event('online')))
    await waitFor(() => expect(sent()).toHaveLength(1))
    onLine.mockReturnValue(false)
    act(() => result.current.remove(id))
    expect(result.current.marks).toHaveLength(0)
    expect(notify.deleted).toHaveBeenCalledWith('highlight', expect.any(Function))
    const undo = notify.deleted.mock.calls[0]?.[1] as () => void
    act(() => undo())
    expect(result.current.marks).toHaveLength(1)
    await waitFor(async () => expect(await waitingWrites(DOC)).toHaveLength(0))
    expect(sent().some((op) => op.op === 'delete')).toBe(false)
  })
})

describe('the cap', () => {
  it('refuses a new mark at the limit and says so, without losing anything', async () => {
    api.batchMarks.mockImplementationOnce(async (_d: string, ops: BatchOpBody[]) => ({
      change_seq: 1,
      marks: { count: 1, limit: 1, near_limit: true },
      results: ops.map((op) => ({ id: op.id, status: 'ok', annotation: makeAnnotation({ id: op.id }) })),
    }))
    const { result } = await open()
    act(() => void result.current.add(draft()))
    await waitFor(() => expect(result.current.info.limit).toBe(1))
    let second: unknown
    act(() => void (second = result.current.add(draft(2))))
    expect(second).toBeNull()
    expect(notify.limitReached).toHaveBeenCalled()
    expect(result.current.notice).toBe('blocked')
    expect(result.current.marks).toHaveLength(1)
  })
})
