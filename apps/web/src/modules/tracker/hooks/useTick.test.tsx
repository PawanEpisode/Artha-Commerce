import { renderHook } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { useTick } from './useStopwatch'

describe('useTick', () => {
  it("ticks on the given window's timers, so a hidden page cannot slow it, and stops with it", () => {
    const other = { setInterval: vi.fn(() => 7), clearInterval: vi.fn() } as unknown as Window
    const mine = vi.spyOn(window, 'setInterval')
    const { unmount } = renderHook(() => useTick(true, 1000, other))
    expect(other.setInterval).toHaveBeenCalledWith(expect.any(Function), 1000)
    expect(mine).not.toHaveBeenCalled()
    unmount()
    expect(other.clearInterval).toHaveBeenCalledWith(7)
    mine.mockRestore()
  })

  it('uses this page by default and does nothing while inactive', () => {
    const mine = vi.spyOn(window, 'setInterval')
    renderHook(() => useTick(false))
    expect(mine).not.toHaveBeenCalled()
    renderHook(() => useTick(true))
    expect(mine).toHaveBeenCalledOnce()
    mine.mockRestore()
  })
})
