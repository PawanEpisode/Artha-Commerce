import { act, renderHook } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const state = vi.hoisted(() => ({ track: vi.fn() }))
vi.mock('~/modules/observability', () => ({ track: state.track }))

import { HOLD_CAP_MS } from '../lib/wakeLock'
import { useWakeLock } from './useWakeLock'

/** A sentinel the test can release the way a browser does (tab hidden, low battery). */
class FakeSentinel extends EventTarget {
  released = false
  release = vi.fn(() => {
    this.released = true
    this.dispatchEvent(new Event('release'))
    return Promise.resolve()
  })
}

let sentinels: FakeSentinel[]
let request: ReturnType<typeof vi.fn>

function stubWakeLock(impl?: () => Promise<FakeSentinel>) {
  sentinels = []
  request = vi.fn(
    impl ??
      (() => {
        const s = new FakeSentinel()
        sentinels.push(s)
        return Promise.resolve(s)
      }),
  )
  Object.defineProperty(navigator, 'wakeLock', { value: { request }, configurable: true })
}

function setVisibility(value: 'visible' | 'hidden') {
  vi.spyOn(document, 'visibilityState', 'get').mockReturnValue(value)
  document.dispatchEvent(new Event('visibilitychange'))
}

const flush = () => act(async () => void (await Promise.resolve()))

beforeEach(() => {
  state.track.mockClear()
  stubWakeLock()
})
afterEach(() => {
  vi.useRealTimers()
  vi.restoreAllMocks()
  Reflect.deleteProperty(navigator, 'wakeLock')
})

describe('useWakeLock', () => {
  it('reports unsupported when the browser has no Wake Lock API', () => {
    Reflect.deleteProperty(navigator, 'wakeLock')
    const { result } = renderHook(() => useWakeLock(true))
    expect(result.current).toBe('unsupported')
  })

  it('stays off, and never asks, while nothing wants the lock', () => {
    const { result } = renderHook(() => useWakeLock(false))
    expect(result.current).toBe('off')
    expect(request).not.toHaveBeenCalled()
  })

  it('requests a screen lock when wanted and says it is held', async () => {
    const { result } = renderHook(() => useWakeLock(true))
    expect(result.current).toBe('checking')
    await flush()
    expect(request).toHaveBeenCalledWith('screen')
    expect(result.current).toBe('held')
  })

  it('releases when it stops being wanted (pause, end, phase end)', async () => {
    const { result, rerender } = renderHook(({ want }) => useWakeLock(want), { initialProps: { want: true } })
    await flush()
    rerender({ want: false })
    expect(sentinels[0]?.release).toHaveBeenCalled()
    expect(result.current).toBe('off')
  })

  it('releases when the component goes away', async () => {
    const { unmount } = renderHook(() => useWakeLock(true))
    await flush()
    unmount()
    expect(sentinels[0]?.released).toBe(true)
  })

  it('shows "sleep" when the browser releases the lock, and asks again when the tab is visible', async () => {
    const { result } = renderHook(() => useWakeLock(true))
    await flush()
    setVisibility('hidden')
    await act(async () => {
      await sentinels[0]?.release()
    })
    expect(result.current).toBe('sleep')
    expect(request).toHaveBeenCalledTimes(1)
    setVisibility('visible')
    await flush()
    expect(request).toHaveBeenCalledTimes(2)
    expect(result.current).toBe('held')
  })

  it('does not ask while the tab is hidden', async () => {
    vi.spyOn(document, 'visibilityState', 'get').mockReturnValue('hidden')
    renderHook(() => useWakeLock(true))
    await flush()
    expect(request).not.toHaveBeenCalled()
  })

  it('treats a refusal as a status, not an error, and reports it once', async () => {
    stubWakeLock(() => Promise.reject(new DOMException('low battery', 'NotAllowedError')))
    const { result } = renderHook(() => useWakeLock(true))
    await flush()
    expect(result.current).toBe('sleep')
    setVisibility('visible')
    await flush()
    expect(state.track).toHaveBeenCalledTimes(1)
    expect(state.track).toHaveBeenCalledWith('keep_awake_refused', {})
  })

  it('does not hold a second lock while one is held', async () => {
    renderHook(() => useWakeLock(true))
    await flush()
    setVisibility('visible')
    await flush()
    expect(request).toHaveBeenCalledTimes(1)
  })

  it('stops holding after four hours and does not ask again (FR-K6)', async () => {
    vi.useFakeTimers()
    const { result } = renderHook(() => useWakeLock(true))
    await flush()
    expect(result.current).toBe('held')
    await act(async () => {
      vi.advanceTimersByTime(HOLD_CAP_MS)
    })
    expect(sentinels[0]?.released).toBe(true)
    expect(result.current).toBe('sleep')
    setVisibility('visible')
    await flush()
    expect(request).toHaveBeenCalledTimes(1)
    expect(state.track).toHaveBeenCalledWith('keep_awake_capped', {})
  })

  it('starts a fresh four hours when the timer is resumed', async () => {
    vi.useFakeTimers()
    const { rerender } = renderHook(({ want }) => useWakeLock(want), { initialProps: { want: true } })
    await flush()
    await act(async () => {
      vi.advanceTimersByTime(HOLD_CAP_MS - 1000)
    })
    rerender({ want: false })
    rerender({ want: true })
    await flush()
    await act(async () => {
      vi.advanceTimersByTime(HOLD_CAP_MS - 1000)
    })
    expect(request).toHaveBeenCalledTimes(2)
    expect(sentinels[1]?.released).toBe(false)
  })
})
