import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, renderHook, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const state = vi.hoisted(() => ({ api: vi.fn(), flag: true }))
vi.mock('~/lib/api', () => ({ api: state.api }))
vi.mock('~/modules/observability', () => ({ track: vi.fn(), useFeatureFlag: () => state.flag }))

import { useKeepAwake } from './useKeepAwake'

const request = vi.fn()
const sentinel = () => Object.assign(new EventTarget(), { release: vi.fn(() => Promise.resolve()) })

function wrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return ({ children }: { children: ReactNode }) => <QueryClientProvider client={qc}>{children}</QueryClientProvider>
}

const RUNNING = { running: true, focus: true }
const flush = () => act(async () => void (await Promise.resolve()))

beforeEach(() => {
  state.api.mockReset().mockResolvedValue({ keep_awake: true, keep_awake_in_breaks: false, volume: 70 })
  state.flag = true
  request.mockReset().mockImplementation(() => Promise.resolve(sentinel()))
  Object.defineProperty(navigator, 'wakeLock', { value: { request }, configurable: true })
})
afterEach(() => Reflect.deleteProperty(navigator, 'wakeLock'))

describe('useKeepAwake', () => {
  it('reads the two switches itself and holds the screen while the stopwatch runs', async () => {
    const { result } = renderHook(() => useKeepAwake(RUNNING), { wrapper: wrapper() })
    await waitFor(() => expect(result.current).toBe('held'))
    expect(state.api).toHaveBeenCalledWith('/focus/settings/')
    expect(request).toHaveBeenCalledWith('screen')
  })

  it('does not even ask for the settings while there is no timer', async () => {
    const { result } = renderHook(() => useKeepAwake(null), { wrapper: wrapper() })
    await flush()
    expect(result.current).toBe('off')
    expect(state.api).not.toHaveBeenCalled()
  })

  it('uses settings it is handed and makes no request of its own', async () => {
    const { result } = renderHook(() => useKeepAwake(RUNNING, { keep_awake: true, keep_awake_in_breaks: false }), {
      wrapper: wrapper(),
    })
    await waitFor(() => expect(result.current).toBe('held'))
    expect(state.api).not.toHaveBeenCalled()
  })

  it('holds nothing when the student has switched it off', async () => {
    state.api.mockResolvedValue({ keep_awake: false, keep_awake_in_breaks: false })
    const { result } = renderHook(() => useKeepAwake(RUNNING), { wrapper: wrapper() })
    await waitFor(() => expect(state.api).toHaveBeenCalled())
    await flush()
    expect(result.current).toBe('off')
    expect(request).not.toHaveBeenCalled()
  })

  it('holds nothing when the settings cannot be read', async () => {
    state.api.mockRejectedValue(new Error('offline'))
    const { result } = renderHook(() => useKeepAwake(RUNNING), { wrapper: wrapper() })
    await waitFor(() => expect(state.api).toHaveBeenCalled())
    await flush()
    expect(result.current).toBe('off')
    expect(request).not.toHaveBeenCalled()
  })

  it('treats a server without the new fields as the defaults: on for focus', async () => {
    state.api.mockResolvedValue({ volume: 70 })
    const { result } = renderHook(() => useKeepAwake(RUNNING), { wrapper: wrapper() })
    await waitFor(() => expect(result.current).toBe('held'))
  })

  it('is switched off by the keep_awake flag, without reading anything', async () => {
    state.flag = false
    const { result } = renderHook(() => useKeepAwake(RUNNING), { wrapper: wrapper() })
    await flush()
    expect(result.current).toBe('off')
    expect(state.api).not.toHaveBeenCalled()
    expect(request).not.toHaveBeenCalled()
  })

  it('releases when the stopwatch is paused', async () => {
    const { result, rerender } = renderHook(({ a }) => useKeepAwake(a), {
      wrapper: wrapper(),
      initialProps: { a: RUNNING as { running: boolean; focus: boolean } | null },
    })
    await waitFor(() => expect(result.current).toBe('held'))
    rerender({ a: { running: false, focus: true } })
    expect(result.current).toBe('off')
  })
})
