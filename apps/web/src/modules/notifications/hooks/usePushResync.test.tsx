import { renderHook, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const state = vi.hoisted(() => ({ flag: true, key: 'KEY' as string | undefined, sync: vi.fn() }))
vi.mock('~/modules/observability', () => ({ useFeatureFlag: () => state.flag }))
vi.mock('~/lib/env', () => ({
  env: {
    get VITE_VAPID_PUBLIC_KEY() {
      return state.key
    },
  },
}))
vi.mock('../lib/register', () => ({ syncCurrentDevice: state.sync }))

import { SW_MESSAGE_SUBSCRIPTION_CHANGED } from '~/sw/messages'

import { markSynced, rememberedDeviceId } from '../lib/deviceMemory'
import { usePushResync } from './usePushResync'

let listener: ((event: MessageEvent) => void) | null = null
const removeEventListener = vi.fn()

beforeEach(() => {
  state.flag = true
  state.key = 'KEY'
  state.sync.mockReset().mockResolvedValue('dev-9')
  removeEventListener.mockReset()
  listener = null
  window.localStorage.clear()
  Object.defineProperty(navigator, 'serviceWorker', {
    configurable: true,
    value: {
      addEventListener: (_type: string, fn: (event: MessageEvent) => void) => (listener = fn),
      removeEventListener,
    },
  })
})

describe('usePushResync', () => {
  it('refreshes this browser once on load and remembers the device id', async () => {
    renderHook(() => usePushResync())
    await waitFor(() => expect(state.sync).toHaveBeenCalledTimes(1))
    await waitFor(() => expect(rememberedDeviceId()).toBe('dev-9'))
  })

  it('skips the refresh when one ran in the last twelve hours', () => {
    markSynced(Date.now() - 60_000)
    renderHook(() => usePushResync())
    expect(state.sync).not.toHaveBeenCalled()
  })

  it('refreshes at once when the worker says the browser rotated its subscription', async () => {
    markSynced(Date.now() - 60_000)
    renderHook(() => usePushResync())
    expect(state.sync).not.toHaveBeenCalled()
    listener?.(new MessageEvent('message', { data: { type: SW_MESSAGE_SUBSCRIPTION_CHANGED, resubscribed: true } }))
    await waitFor(() => expect(state.sync).toHaveBeenCalledTimes(1))
  })

  it('ignores other messages', () => {
    renderHook(() => usePushResync())
    state.sync.mockClear()
    listener?.(new MessageEvent('message', { data: { type: 'something-else' } }))
    expect(state.sync).not.toHaveBeenCalled()
  })

  it('does nothing without the flag or without a VAPID key', () => {
    state.flag = false
    renderHook(() => usePushResync())
    state.flag = true
    state.key = undefined
    renderHook(() => usePushResync())
    expect(state.sync).not.toHaveBeenCalled()
    expect(listener).toBeNull()
  })

  it('stays quiet when registering fails, and stops listening on unmount', async () => {
    state.sync.mockRejectedValue(new Error('401'))
    const { unmount } = renderHook(() => usePushResync())
    await waitFor(() => expect(state.sync).toHaveBeenCalled())
    expect(rememberedDeviceId()).toBeNull()
    unmount()
    expect(removeEventListener).toHaveBeenCalled()
  })
})
