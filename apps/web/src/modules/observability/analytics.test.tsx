import { act, renderHook } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const ph = vi.hoisted(() => ({
  __loaded: false,
  value: true as boolean | undefined,
  listeners: [] as Array<() => void>,
  onFeatureFlags(cb: () => void) {
    ph.listeners.push(cb)
    return () => {
      ph.listeners = ph.listeners.filter((l) => l !== cb)
    }
  },
  isFeatureEnabled: () => ph.value,
  capture: vi.fn(),
}))
vi.mock('posthog-js', () => ({ default: ph }))

import { useFeatureFlag } from './analytics'

describe('useFeatureFlag', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    ph.__loaded = false
    ph.value = true
    ph.listeners = []
  })
  afterEach(() => vi.useRealTimers())

  it('a strict flag turns on when PostHog finishes loading after the first render', () => {
    const { result } = renderHook(() => useFeatureFlag('recall_system', { strict: true }))
    expect(result.current).toBe(false)
    act(() => {
      ph.__loaded = true
      vi.advanceTimersByTime(200)
    })
    act(() => ph.listeners.forEach((l) => l()))
    expect(result.current).toBe(true)
  })

  it('a strict flag stays off when PostHog says it is off or never loads', () => {
    const { result } = renderHook(() => useFeatureFlag('recall_system', { strict: true }))
    act(() => vi.advanceTimersByTime(11_000))
    expect(result.current).toBe(false)
  })

  it('an ordinary flag stays on until PostHog says false', () => {
    ph.__loaded = true
    ph.value = undefined
    const { result } = renderHook(() => useFeatureFlag('notes'))
    act(() => ph.listeners.forEach((l) => l()))
    expect(result.current).toBe(true)
    ph.value = false
    act(() => ph.listeners.forEach((l) => l()))
    expect(result.current).toBe(false)
  })
})
