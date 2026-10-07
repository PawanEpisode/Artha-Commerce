import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { renderHook, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '~/lib/api'

const state = vi.hoisted(() => ({ flag: true, getTodayThought: vi.fn() }))

vi.mock('~/modules/observability', () => ({ track: vi.fn(), useFeatureFlag: () => state.flag }))
vi.mock('../lib/api', async (original) => ({
  ...(await original<Record<string, unknown>>()),
  getTodayThought: state.getTodayThought,
}))

import { useTodayThought } from './useTodayThought'

const thought = { id: 'm1', body: 'Start small.', attribution: null, shown_on: '2026-10-07' }
let client: QueryClient
const wrapper = ({ children }: { children: ReactNode }) => (
  <QueryClientProvider client={client}>{children}</QueryClientProvider>
)

beforeEach(() => {
  state.flag = true
  state.getTodayThought.mockReset()
  client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
})

describe('useTodayThought', () => {
  it('returns the thought and is not off', async () => {
    state.getTodayThought.mockResolvedValue(thought)
    const { result } = renderHook(() => useTodayThought(), { wrapper })
    await waitFor(() => expect(result.current.thought).toEqual(thought))
    expect(result.current.off).toBe(false)
  })

  it('is off, and asks nothing, when the flag is off', () => {
    state.flag = false
    const { result } = renderHook(() => useTodayThought(), { wrapper })
    expect(result.current.off).toBe(true)
    expect(state.getTodayThought).not.toHaveBeenCalled()
  })

  it('is off when the server has no thought for this student', async () => {
    state.getTodayThought.mockResolvedValue(null)
    const { result } = renderHook(() => useTodayThought(), { wrapper })
    await waitFor(() => expect(result.current.off).toBe(true))
  })

  it('is off when the server says notifications are off for this student', async () => {
    state.getTodayThought.mockRejectedValue(new ApiError(403, 'off', { error: { code: 'notifications_disabled' } }))
    const { result } = renderHook(() => useTodayThought(), { wrapper })
    await waitFor(() => expect(result.current.off).toBe(true))
    expect(state.getTodayThought).toHaveBeenCalledTimes(1)
  })
})
