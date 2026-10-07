import { renderHook } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { useAppBadge } from './useAppBadge'

const set = vi.fn().mockResolvedValue(undefined)
const clear = vi.fn().mockResolvedValue(undefined)

beforeEach(() => {
  set.mockClear()
  clear.mockClear()
  Object.assign(navigator, { setAppBadge: set, clearAppBadge: clear })
})
afterEach(() => {
  Reflect.deleteProperty(navigator, 'setAppBadge')
  Reflect.deleteProperty(navigator, 'clearAppBadge')
})

describe('useAppBadge', () => {
  it('follows the timer state: dot while it runs, cleared when idle', () => {
    const hook = renderHook(({ on }) => useAppBadge(on), { initialProps: { on: true } })
    expect(set).toHaveBeenCalledOnce()
    hook.rerender({ on: false })
    expect(clear).toHaveBeenCalledOnce()
  })

  it('clears the dot when it goes away (signed out, flag off, page left)', () => {
    const hook = renderHook(() => useAppBadge(true))
    hook.unmount()
    expect(clear).toHaveBeenCalled()
  })
})
