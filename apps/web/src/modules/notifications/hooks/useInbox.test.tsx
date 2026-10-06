import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, renderHook, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '~/lib/api'

const state = vi.hoisted(() => ({ flag: true, getInbox: vi.fn(), postInboxRead: vi.fn() }))

vi.mock('~/modules/observability', () => ({ track: vi.fn(), useFeatureFlag: () => state.flag }))
vi.mock('../lib/api', async (original) => ({
  ...(await original<Record<string, unknown>>()),
  getInbox: state.getInbox,
  postInboxRead: state.postInboxRead,
}))

import { notificationKeys } from '../lib/keys'
import type { InboxItem, InboxPage } from '../lib/schemas'
import { useBellCount, useInboxList, useMarkInboxRead } from './useInbox'

const item = (id: string, read = false): InboxItem => ({
  id,
  category: 'timer',
  category_label: 'Timer alerts',
  title: id,
  body: '',
  deep_link: '/app/focus',
  read,
  created_at: '2026-10-05T04:30:00Z',
})
const answer = (unread: number, results: InboxItem[] = [], next: string | null = null): InboxPage => ({
  results,
  next_cursor: next,
  unread_count: unread,
})

let client: QueryClient
const wrapper = ({ children }: { children: ReactNode }) => (
  <QueryClientProvider client={client}>{children}</QueryClientProvider>
)

class FakeServiceWorker extends EventTarget {}
let worker: FakeServiceWorker
const post = (data: unknown) => act(() => void worker.dispatchEvent(new MessageEvent('message', { data })))

beforeEach(() => {
  client = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: 60_000, refetchOnWindowFocus: false } },
  })
  state.flag = true
  state.getInbox.mockReset().mockResolvedValue(answer(2))
  state.postInboxRead.mockReset()
  worker = new FakeServiceWorker()
  Object.defineProperty(navigator, 'serviceWorker', { value: worker, configurable: true })
})

afterEach(() => {
  vi.useRealTimers()
  Reflect.deleteProperty(navigator, 'serviceWorker')
})

describe('useBellCount', () => {
  it('asks for one item and returns only the unread count', async () => {
    const { result } = renderHook(() => useBellCount(), { wrapper })
    expect(result.current).toEqual({ unread: null, off: false })
    await waitFor(() => expect(result.current.unread).toBe(2))
    expect(state.getInbox).toHaveBeenCalledWith({ limit: 1 })
  })

  it('polls every 60 seconds and not before', async () => {
    vi.useFakeTimers()
    renderHook(() => useBellCount(), { wrapper })
    await vi.advanceTimersByTimeAsync(0)
    expect(state.getInbox).toHaveBeenCalledTimes(1)
    await vi.advanceTimersByTimeAsync(59_000)
    expect(state.getInbox).toHaveBeenCalledTimes(1)
    await vi.advanceTimersByTimeAsync(1_000)
    expect(state.getInbox).toHaveBeenCalledTimes(2)
    await vi.advanceTimersByTimeAsync(60_000)
    expect(state.getInbox).toHaveBeenCalledTimes(3)
  })

  it('shows a count that rose at the next poll', async () => {
    vi.useFakeTimers()
    const { result } = renderHook(() => useBellCount(), { wrapper })
    await act(() => vi.advanceTimersByTimeAsync(0))
    expect(result.current.unread).toBe(2)
    state.getInbox.mockResolvedValue(answer(5))
    await act(() => vi.advanceTimersByTimeAsync(60_000))
    await act(() => vi.advanceTimersByTimeAsync(50)) // the query cache hands the answer to the hook on its own tick
    expect(result.current.unread).toBe(5)
  })

  it('refetches when the window gets focus again, even inside the stale time', async () => {
    const { result } = renderHook(() => useBellCount(), { wrapper })
    await waitFor(() => expect(result.current.unread).toBe(2))
    state.getInbox.mockResolvedValue(answer(7))
    act(() => void window.dispatchEvent(new Event('visibilitychange')))
    await waitFor(() => expect(result.current.unread).toBe(7))
    expect(state.getInbox).toHaveBeenCalledTimes(2)
  })

  it('refetches at once when the worker says a push arrived', async () => {
    const { result } = renderHook(() => useBellCount(), { wrapper })
    await waitFor(() => expect(result.current.unread).toBe(2))
    state.getInbox.mockResolvedValue(answer(3))
    post({ type: 'artha:push-received' })
    await waitFor(() => expect(result.current.unread).toBe(3))
    expect(state.getInbox).toHaveBeenCalledTimes(2)
  })

  it('ignores worker messages that are not about a push, and malformed ones', async () => {
    const { result } = renderHook(() => useBellCount(), { wrapper })
    await waitFor(() => expect(result.current.unread).toBe(2))
    post({ type: 'artha:push-subscription-changed', resubscribed: true })
    post('artha:push-received')
    post(null)
    await act(async () => undefined)
    expect(state.getInbox).toHaveBeenCalledTimes(1)
  })

  it('stops listening to the worker when it unmounts', async () => {
    const { result, unmount } = renderHook(() => useBellCount(), { wrapper })
    await waitFor(() => expect(result.current.unread).toBe(2))
    unmount()
    post({ type: 'artha:push-received' })
    expect(state.getInbox).toHaveBeenCalledTimes(1)
  })

  it('does nothing, and reports off, while the notifications_ui flag is off', async () => {
    state.flag = false
    vi.useFakeTimers()
    const { result } = renderHook(() => useBellCount(), { wrapper })
    await vi.advanceTimersByTimeAsync(180_000)
    post({ type: 'artha:push-received' })
    expect(state.getInbox).not.toHaveBeenCalled()
    expect(result.current).toEqual({ unread: null, off: true })
  })

  it('goes off and stops polling for good on 403 notifications_disabled', async () => {
    vi.useFakeTimers()
    state.getInbox.mockRejectedValue(new ApiError(403, 'off', { error: { code: 'notifications_disabled' } }))
    const { result } = renderHook(() => useBellCount(), { wrapper })
    await vi.advanceTimersByTimeAsync(0)
    expect(result.current.off).toBe(true)
    await vi.advanceTimersByTimeAsync(300_000)
    expect(state.getInbox).toHaveBeenCalledTimes(1)
  })

  it('keeps the bell and the last count through a failed poll', async () => {
    vi.useFakeTimers()
    const { result } = renderHook(() => useBellCount(), { wrapper })
    await act(() => vi.advanceTimersByTimeAsync(0))
    state.getInbox.mockRejectedValue(new ApiError(500, 'boom'))
    await act(() => vi.advanceTimersByTimeAsync(60_000))
    expect(result.current).toEqual({ unread: 2, off: false })
  })
})

describe('useInboxList', () => {
  it('pages with the cursor the server gave', async () => {
    state.getInbox
      .mockResolvedValueOnce(answer(3, [item('a'), item('b')], 'next-1'))
      .mockResolvedValueOnce(answer(3, [item('c')]))
    const { result } = renderHook(() => useInboxList(), { wrapper })
    await waitFor(() => expect(result.current.data?.pages).toHaveLength(1))
    expect(state.getInbox).toHaveBeenLastCalledWith({ cursor: null, limit: 20 })
    expect(result.current.hasNextPage).toBe(true)
    await act(async () => void (await result.current.fetchNextPage()))
    expect(state.getInbox).toHaveBeenLastCalledWith({ cursor: 'next-1', limit: 20 })
    await waitFor(() => expect(result.current.data?.pages).toHaveLength(2))
    expect(result.current.hasNextPage).toBe(false)
  })

  it('is refreshed by a worker push message through the shared key', async () => {
    const bell = renderHook(() => useBellCount(), { wrapper })
    const list = renderHook(() => useInboxList(), { wrapper })
    await waitFor(() => expect(bell.result.current.unread).toBe(2))
    await waitFor(() => expect(list.result.current.data).toBeDefined())
    const before = state.getInbox.mock.calls.length
    post({ type: 'artha:push-received' })
    await waitFor(() => expect(state.getInbox.mock.calls.length).toBe(before + 2)) // the bell and the list
  })
})

describe('useMarkInboxRead', () => {
  const seed = () => {
    client.setQueryData(notificationKeys.inboxList, {
      pages: [answer(2, [item('a'), item('b'), item('c', true)])],
      pageParams: [null],
    })
    client.setQueryData(notificationKeys.bell, answer(2))
  }
  const list = () => client.getQueryData<{ pages: InboxPage[] }>(notificationKeys.inboxList)

  it('marks the items and lowers the bell at once, then takes the server count', async () => {
    seed()
    let release: (n: number) => void = () => undefined
    state.postInboxRead.mockReturnValue(new Promise<number>((resolve) => (release = resolve)))
    const { result } = renderHook(() => useMarkInboxRead(), { wrapper })
    act(() => result.current.mutate({ ids: ['a'] }))
    await waitFor(() => expect(list()?.pages[0]?.results[0]?.read).toBe(true))
    expect(client.getQueryData<InboxPage>(notificationKeys.bell)?.unread_count).toBe(1)
    expect(state.postInboxRead).toHaveBeenCalledWith({ ids: ['a'] })
    release(1)
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
  })

  it('marks all and zeroes the count', async () => {
    seed()
    state.postInboxRead.mockResolvedValue(0)
    const { result } = renderHook(() => useMarkInboxRead(), { wrapper })
    act(() => result.current.mutate({ all: true }))
    await waitFor(() => expect(client.getQueryData<InboxPage>(notificationKeys.bell)?.unread_count).toBe(0))
    expect(list()?.pages[0]?.results.every((i) => i.read)).toBe(true)
  })

  it('puts everything back when the request fails', async () => {
    seed()
    state.postInboxRead.mockRejectedValue(new ApiError(500, 'boom'))
    const { result } = renderHook(() => useMarkInboxRead(), { wrapper })
    act(() => result.current.mutate({ ids: ['a'] }))
    await waitFor(() => expect(result.current.isError).toBe(true))
    expect(list()?.pages[0]?.results[0]?.read).toBe(false)
    expect(client.getQueryData<InboxPage>(notificationKeys.bell)?.unread_count).toBe(2)
  })
})
