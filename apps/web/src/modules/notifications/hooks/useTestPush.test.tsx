import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, renderHook, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const state = vi.hoisted(() => ({ send: vi.fn(), track: vi.fn() }))
vi.mock('../lib/api', async (original) => ({
  ...(await original<Record<string, unknown>>()),
  sendTestPush: state.send,
}))
vi.mock('~/modules/observability', () => ({ track: state.track }))

import { ApiError } from '~/lib/api'

import type { NotificationDevice } from '../lib/schemas'
import { useTestPush } from './useTestPush'

const device: NotificationDevice = {
  id: 'd1',
  label: 'Chrome',
  platform: 'android',
  browser: 'chrome',
  display_mode: 'browser',
  last_seen_at: null,
}
const wrapper = ({ children }: { children: ReactNode }) => (
  <QueryClientProvider client={new QueryClient({ defaultOptions: { mutations: { retry: false } } })}>
    {children}
  </QueryClientProvider>
)
const throttled = (seconds: number) => {
  const error = new ApiError(429, 'x')
  error.retryAfter = seconds
  return error
}

beforeEach(() => {
  state.send.mockReset()
  state.track.mockClear()
})
afterEach(() => vi.useRealTimers())

describe('useTestPush', () => {
  it('cannot send without a device', () => {
    const { result } = renderHook(() => useTestPush([], null, vi.fn()), { wrapper })
    expect(result.current.canSend).toBe(false)
    act(() => result.current.send())
    expect(state.send).not.toHaveBeenCalled()
  })

  it('sends to the device and reports success', async () => {
    state.send.mockResolvedValue(undefined)
    const { result } = renderHook(() => useTestPush([device], 'd1', vi.fn()), { wrapper })
    act(() => result.current.send())
    expect(result.current.status.kind).toBe('sending')
    await waitFor(() => expect(result.current.status.kind).toBe('sent'))
    expect(state.send).toHaveBeenCalledWith('d1')
    expect(state.track).toHaveBeenCalledWith('push_test_requested', { platform: 'android' })
    expect(result.current.canSend).toBe(true)
  })

  it('ignores a second tap while one is in flight', async () => {
    state.send.mockReturnValue(new Promise(() => undefined))
    const { result } = renderHook(() => useTestPush([device], 'd1', vi.fn()), { wrapper })
    act(() => {
      result.current.send()
      result.current.send()
    })
    await waitFor(() => expect(state.send).toHaveBeenCalledTimes(1))
    expect(state.track).toHaveBeenCalledTimes(1)
  })

  it('rests after a 429 for the time the API asked, then comes back by itself', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    state.send.mockRejectedValue(throttled(20))
    const { result } = renderHook(() => useTestPush([device], 'd1', vi.fn()), { wrapper })
    act(() => result.current.send())
    await waitFor(() => expect(result.current.status).toEqual({ kind: 'rate_limited', seconds: 20 }))
    expect(result.current.canSend).toBe(false)
    act(() => result.current.send())
    expect(state.send).toHaveBeenCalledTimes(1)

    await act(async () => {
      await vi.advanceTimersByTimeAsync(19_000)
    })
    expect(result.current.canSend).toBe(false)
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1_500)
    })
    expect(result.current.status.kind).toBe('idle')
    expect(result.current.canSend).toBe(true)
  })

  it('asks the caller to reload the list when the device is gone', async () => {
    state.send.mockRejectedValue(new ApiError(404, 'x'))
    const onGone = vi.fn()
    const { result } = renderHook(() => useTestPush([device], 'd1', onGone), { wrapper })
    act(() => result.current.send())
    await waitFor(() => expect(result.current.status.kind).toBe('device_gone'))
    expect(onGone).toHaveBeenCalledTimes(1)
  })
})
